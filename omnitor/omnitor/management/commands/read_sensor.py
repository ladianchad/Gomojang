import os
import sys
import serial
import time
import math
import minimalmodbus
import serial.tools.list_ports
from collections import deque
from datetime import datetime
from django.core.management.base import BaseCommand
from omnitor.omnitor.models.models import SensorData, CalibrationSettings

# --- 설정 ---
BAUDRATE = 9600
MODBUS_PORT = '/dev/ttyUSB0'
MODBUS_ADDRESS = 1
MOVING_AVERAGE_WINDOW = 5 # Number of data points to average
SAVE_INTERVAL_SECONDS = 60 # Save data every 60 seconds
LOOP_SLEEP_SECONDS = 0.1 # Reads sensor data every 0.1 sec
tip_capacity = 5 # Tipping gauge water capacity = 5mL

# 연결된 시리얼 포트들을 검색해서 Arduino가 포함된 포트 경로를 반환
# 못 찾으면 기본값 '/dev/ttyACM0'를 반환
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        if "Arduino" in port.description:
            return port.device
            
        if "ACM" in port.device:
            return port.device   
    
    return '/dev/ttyACM0'

#
class Command(BaseCommand):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 이동 평균 필터를 위한 디큐
        self.data_history = {
            'air_temperature': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'air_humidity': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'co2': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'insolation': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'weight_raw': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'ph_voltage': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'ec_voltage': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'water_temperature': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'soil_humidity': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'soil_temperature': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'soil_conductivity': deque(maxlen=MOVING_AVERAGE_WINDOW),
            'soil_ph': deque(maxlen=MOVING_AVERAGE_WINDOW),
        }
        self.last_save_time = 0.0
        self.latest_smoothed_data = None
        self.daily_baseline_tip_count = None # 자정 시점의 아두이노 누적 카운트
        self.last_reset_date = None # 마지막으로 리셋한 날짜

    def apply_smoothing(self, data_dict):
        """Applies a moving average to new data and returns the smoothed values."""
        smoothed_data = {}
        for key, value in data_dict.items():
            if key in self.data_history and value is not None:
                self.data_history[key].append(value)
                current_deque = self.data_history[key]
                smoothed_value = sum(current_deque) / len(current_deque)
                smoothed_data[key] = smoothed_value
            else:
                smoothed_data[key] = value
        return smoothed_data

    def parse_arduino_data(self, serial_line, settings):
        """
        아두이노에서 데이터를 받아서 필터 적용 & 보정
        데이터 포맷: "AirTemp,AirHum,CO2,Insolation,Weight_Raw,pH_V,EC_V,WaterTemp,TipCount"
        """
        try:
            self.stdout.write(f"[Arduino RAW]: {serial_line.strip()}")
            parts = serial_line.strip().split(',')
            if len(parts) == 9:
                raw_data = {
                    'air_temperature': float(parts[0]),
                    'air_humidity': float(parts[1]),
                    'co2': float(parts[2]),
                    'insolation': float(parts[3]),
                    'weight_raw': float(parts[4]),
                    'ph_voltage': float(parts[5]),
                    'ec_voltage': float(parts[6]),
                    'water_temperature': float(parts[7]),
                }

                tip_count = float(parts[8])

                import json
                state_file_path = '/tmp/sensor_state.json' # 리눅스 임시 폴더 사용
                
                try:
                    with open(state_file_path, 'w') as f:
                        json.dump(raw_data, f)
                except Exception as e:
                    self.stdout.write(f"Error writing state file: {e}")
                
                # Apply moving average filter to raw data first
                smoothed_raw_data = self.apply_smoothing(raw_data)
                smoothed_raw_data['tip_count'] = tip_count
                
                calibrated_data = {}
                
                # 무게 2점 보정
                w_raw = smoothed_raw_data['weight_raw']
                w_p1_r = settings.weight_point1_raw
                w_p1_v = settings.weight_point1_value
                w_p2_r = settings.weight_point2_raw
                w_p2_v = settings.weight_point2_value

                if (w_p2_r - w_p1_r) != 0:
                    w_slope = (w_p2_v - w_p1_v) / (w_p2_r - w_p1_r)
                    w_intercept = w_p1_v - (w_slope * w_p1_r)
                    calibrated_data['weight_calibrated'] = (w_slope * w_raw) + w_intercept
                else:
                    calibrated_data['weight_calibrated'] = 0

                # ph, ec 보정에 필요한 수온 변수
                current_water_temp = smoothed_raw_data.get('water_temperature', 25.0)

                # ph 보정 (온도 보정 포함)
                ph_volts = smoothed_raw_data['ph_voltage']
                
                ph1_val_adj = settings.ph_point1_value - 0.017 * (current_water_temp - 25.0)
                ph2_val_adj = settings.ph_point2_value - 0.017 * (current_water_temp - 25.0)
                
                ph_v1 = settings.ph_point1_voltage
                ph_v2 = settings.ph_point2_voltage
                
                if (ph_v2 - ph_v1) != 0:
                    ph_slope = (ph2_val_adj - ph1_val_adj) / (ph_v2 - ph_v1)
                    ph_intercept = ph1_val_adj - (ph_slope * ph_v1)
                    
                    calibrated_data['ph_calibrated'] = (ph_slope * ph_volts) + ph_intercept
                else:
                    calibrated_data['ph_calibrated'] = 0.0


                # EC 보정 (온도 보정 포함)
                ec_volts = smoothed_raw_data['ec_voltage']
                
                ec1_val_adj = settings.ec_point1_value * (1.0 + 0.02 * (current_water_temp - 25.0))
                ec2_val_adj = settings.ec_point2_value * (1.0 + 0.02 * (current_water_temp - 25.0))

                ec_v1 = settings.ec_point1_voltage
                ec_v2 = settings.ec_point2_voltage

                if (ec_v2 - ec_v1) != 0:
                    ec_slope = (ec2_val_adj - ec1_val_adj) / (ec_v2 - ec_v1)
                    ec_intercept = ec1_val_adj - (ec_slope * ec_v1)
                    
                    calibrated_data['ec_calibrated'] = (ec_slope * ec_volts) + ec_intercept
                else:
                    calibrated_data['ec_calibrated'] = 0.0
                    
                # 원본 raw 데이터와 최종 보정 데이터를 모두 반환
                return {**raw_data, **smoothed_raw_data, **calibrated_data}
            
            else:
                self.stdout.write(self.style.WARNING(f"Warning: Incorrect Arduino data format. (Received {len(parts)} items, expected 8)"))
                return None
        except (ValueError, IndexError) as e:
            self.stderr.write(self.style.ERROR(f"Error: Could not parse Arduino data - {e}"))
            return None

    def read_modbus_sensor(self, instrument):
        """토양 센서에서 데이터를 읽고 필터 적용용"""
        try:
            data = instrument.read_registers(0, 4, 3)
            self.stdout.write(f"[Modbus RAW]: {data}")
            raw_soil_data = {
                'soil_humidity': data[0] / 10.0,
                'soil_temperature': data[1] / 10.0,
                'soil_conductivity': float(data[2]),
                'soil_ph': data[3] / 10.0
            }
            return self.apply_smoothing(raw_soil_data)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Modbus Read Error: {e}"))
            return None

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Initializing sensors..."))

        found_port = find_arduino_port()
        self.stdout.write(f"Detected Arduino port: {found_port}")
        
        try:
            arduino_ser = serial.Serial(found_port, BAUDRATE, timeout=1)
            time.sleep(2)
            arduino_ser.reset_input_buffer()
            self.stdout.write(self.style.SUCCESS(f"Success: Connected to Arduino on {found_port}."))
        except serial.SerialException as e:
            self.stderr.write(self.style.ERROR(f"Arduino connection failed: {e}. Exiting."))
            return

        instrument = None
        try:
            instrument = minimalmodbus.Instrument(MODBUS_PORT, MODBUS_ADDRESS, mode='rtu')
            instrument.serial.baudrate = 4800
            instrument.serial.timeout = 1
            instrument.serial.close_port_after_each_call = True
            self.stdout.write(self.style.SUCCESS(f"Success: Modbus instrument configured for {MODBUS_PORT}."))
        except serial.SerialException as e:
            self.stderr.write(self.style.WARNING(f"Modbus connection failed: {e}. Soil data will be unavailable."))

        self.stdout.write(self.style.SUCCESS(f"\nStarting data reception. Saving to DB every {SAVE_INTERVAL_SECONDS} seconds. Press Ctrl+C to exit."))
        
        self.last_save_time = time.time() # reset save timer

        while True:
            try:
                settings = CalibrationSettings.load()

                if arduino_ser.in_waiting > 0:
                    line = arduino_ser.readline().decode('utf-8')
                    arduino_data = self.parse_arduino_data(line, settings)
                    
                    if arduino_data:
                        soil_data = None
                        if instrument:
                            soil_data = self.read_modbus_sensor(instrument)
                        
                        all_data = {**arduino_data}
                        if soil_data:
                            all_data.update(soil_data)

                        # save latest smoothed data to class variable
                        self.latest_smoothed_data = all_data

                current_time = time.time()
                if (current_time - self.last_save_time) >= SAVE_INTERVAL_SECONDS:
                    if self.latest_smoothed_data:
                        try:
                            data_to_save = {}
                            for key, value in self.latest_smoothed_data.items():
                                val = self.latest_smoothed_data.get(key)
                                if isinstance(val, (int, float)):
                                    # Don't apply max(0) to temperatures
                                    if 'temperature' in key:
                                        data_to_save[key] = val
                                    else:
                                        data_to_save[key] = max(0, val or 0)
                                else:
                                    data_to_save[key] = val

                            today = datetime.now().date()
                            current_arduino_total_count = data_to_save.get('tip_count') # (예: 502)
                            daily_tip_count = 0.0 # (오늘 하루 누적 팁 횟수, 기본값 0)
                            
                            if current_arduino_total_count is not None:
                                # 1. 자정 리셋: 스크립트 첫 실행이거나 날짜가 바뀌었으면
                                if self.last_reset_date is None or self.last_reset_date != today:
                                    self.stdout.write(self.style.SUCCESS(f"--- 🗓️ 자정 리셋: 새 기준 팁 횟수 {current_arduino_total_count} 설정 ---"))
                                    self.daily_baseline_tip_count = current_arduino_total_count # '자정 기준' (예: 500)
                                    self.last_reset_date = today
                                
                                # 2. '자정 기준' 값이 설정되었다면
                                if self.daily_baseline_tip_count is not None:
                                    # 3. 아두이노 리셋 감지
                                    if current_arduino_total_count < self.daily_baseline_tip_count:
                                        self.stdout.write(self.style.WARNING(f"--- 아두이노 리셋 감지: 기준 {self.daily_baseline_tip_count} > 현재 {current_arduino_total_count}. 기준을 {current_arduino_total_count}로 리셋 ---"))
                                        self.daily_baseline_tip_count = current_arduino_total_count
                                    
                                    # 4. 오늘 누적 팁 횟수 = (현재 총 횟수 - 기준 횟수)
                                    daily_tip_count = current_arduino_total_count - self.daily_baseline_tip_count
                                
                            # 5. 일일 누적 배액량(mL) 계산
                            tip_total_to_save = daily_tip_count * tip_capacity
                            
                            SensorData.objects.create(
                                air_temperature=data_to_save.get('air_temperature'),
                                air_humidity=data_to_save.get('air_humidity'),
                                co2=data_to_save.get('co2'),
                                insolation=data_to_save.get('insolation'),
                                water_temperature=data_to_save.get('water_temperature'),
                                weight_raw=data_to_save.get('weight_raw'),
                                weight_calibrated=data_to_save.get('weight_calibrated'),
                                ph_voltage=data_to_save.get('ph_voltage'),
                                ph_calibrated=data_to_save.get('ph_calibrated'),
                                ec_voltage=data_to_save.get('ec_voltage'),
                                ec_calibrated=data_to_save.get('ec_calibrated'),
                                tip_count=data_to_save.get('tip_count'),
                                tip_total=tip_total_to_save,
                                soil_temperature=data_to_save.get('soil_temperature'),
                                soil_humidity=data_to_save.get('soil_humidity'),
                                soil_conductivity=data_to_save.get('soil_conductivity'),
                                soil_ph=data_to_save.get('soil_ph'),
                            )
                            
                            self.stdout.write(self.style.SUCCESS(f"Saved 1-minute data at {time.strftime('%Y-%m-%d %H:%M:%S')}"))
                            
                            self.latest_smoothed_data = None
                        
                        except Exception as db_e:
                            self.stderr.write(self.style.ERROR(f"Database save error: {db_e}"))
                    
                    else:
                        self.stdout.write(self.style.WARNING(f"No new sensor data read in the last minute. Skipping save."))

                    self.last_save_time = current_time 
                
                time.sleep(LOOP_SLEEP_SECONDS) 

            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS("\nExiting."))
                break
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"An unexpected error occurred in the main loop: {e}"))
                time.sleep(5)
        
        if arduino_ser.is_open:
            arduino_ser.close()
            self.stdout.write(self.style.SUCCESS("Arduino serial port closed."))

