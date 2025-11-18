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
from omnitor.models import SensorData, CalibrationSettings

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
        Parses a comma-separated line from Arduino, applies smoothing and all calibrations.
        Format: "AirTemp,AirHum,CO2,Insolation,Weight_Raw,pH_V,EC_V,WaterTemp,TipCount"
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
                
                # Weight calibration
                calibrated_data['weight_calibrated'] = (smoothed_raw_data['weight_raw'] * settings.weight_slope) + settings.weight_intercept if settings.weight_slope is not None and settings.weight_intercept is not None else 0
                
                # pH Calibration (2-point + temperature compensation)
                base_ph = (smoothed_raw_data['ph_voltage'] * settings.ph_slope) + settings.ph_intercept
                temp_diff = smoothed_raw_data['water_temperature'] - 25.0
                ph_compensation = 0.017 * temp_diff
                calibrated_data['ph_calibrated'] = base_ph - ph_compensation

                # EC Calibration (temp compensation + formula + 2-point)
                temp_coeff = 1.0 + 0.02 * temp_diff
                compensated_ec_voltage = smoothed_raw_data['ec_voltage'] / temp_coeff if temp_coeff != 0 else 0
                v = compensated_ec_voltage
                base_ec = (133.42 * math.pow(v, 3)) - (255.86 * math.pow(v, 2)) + (857.39 * v)
                calibrated_data['ec_calibrated'] = (base_ec * settings.ec_slope) + settings.ec_intercept

                # Return original raw data and the final calibrated data
                # 원본 raw 데이터와 최종 보정 데이터를 모두 반환
                return {**raw_data, **smoothed_raw_data, **calibrated_data}
            
            else:
                self.stdout.write(self.style.WARNING(f"Warning: Incorrect Arduino data format. (Received {len(parts)} items, expected 8)"))
                return None
        except (ValueError, IndexError) as e:
            self.stderr.write(self.style.ERROR(f"Error: Could not parse Arduino data - {e}"))
            return None

    def read_modbus_sensor(self, instrument):
        """Reads data from the Modbus soil sensor and applies smoothing."""
        try:
            data = instrument.read_registers(0, 4, 3)
            self.stdout.write(f"[Modbus RAW]: {data}")
            raw_soil_data = {
                'soil_humidity': data[0] / 10.0,
                'soil_temperature': data[1] / 10.0,
                'soil_conductivity': float(data[2]),
                'soil_ph': data[3] / 10.0
            }
            # Apply moving average to soil data
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
                # Load latest calibration settings in each loop
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

                # --- save data every 1 min ---
                current_time = time.time()
                if (current_time - self.last_save_time) >= SAVE_INTERVAL_SECONDS:
                    if self.latest_smoothed_data:
                        try:
                            # if value is less than 0, just make it 0
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
                            
                            # reset for next data
                            self.latest_smoothed_data = None
                        
                        except Exception as db_e:
                            self.stderr.write(self.style.ERROR(f"Database save error: {db_e}"))
                    
                    else:
                        # if there is no new data read in the last 1 min
                        self.stdout.write(self.style.WARNING(f"No new sensor data read in the last minute. Skipping save."))

                    # reset timer
                    self.last_save_time = current_time 
                
                # loop to not use CPU 100%
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

