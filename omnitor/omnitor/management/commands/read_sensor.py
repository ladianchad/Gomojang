import os
import sys
import serial
import time
import math
import minimalmodbus
from collections import deque
from django.core.management.base import BaseCommand
from omnitor.models import SensorData, CalibrationSettings

# --- Settings ---
ARDUINO_PORT = '/dev/ttyACM0'
BAUDRATE = 9600
MODBUS_PORT = '/dev/ttyUSB0'
MODBUS_ADDRESS = 1
MOVING_AVERAGE_WINDOW = 5 # Number of data points to average

class Command(BaseCommand):
    help = 'Reads data from Arduino and Modbus, applies a moving average filter and calibration, and saves to the database.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize deques for the moving average filter
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
        Format: "AirTemp,AirHum,CO2,Insolation,Weight_Raw,pH_V,EC_V,WaterTemp"
        """
        try:
            parts = serial_line.strip().split(',')
            if len(parts) == 8:
                raw_data = {
                    'air_temperature': float(parts[0]),
                    'air_humidity': float(parts[1]),
                    'co2': float(parts[2]),
                    'insolation': float(parts[3]), # Changed from lux
                    'weight_raw': float(parts[4]),
                    'ph_voltage': float(parts[5]),
                    'ec_voltage': float(parts[6]),
                    'water_temperature': float(parts[7]),
                }

                # Apply moving average filter to raw data first
                smoothed_raw_data = self.apply_smoothing(raw_data)
                calibrated_data = {}
                
                # Weight calibration
                calibrated_data['weight_calibrated'] = (smoothed_raw_data['weight_raw'] - settings.weight_offset) / settings.weight_scale if settings.weight_scale != 0 else 0

                # pH Calibration (2-point + temperature compensation)
                base_ph = (smoothed_raw_data['ph_voltage'] * settings.ph_slope) + settings.ph_intercept
                temp_diff = smoothed_raw_data['water_temperature'] - 25.0
                ph_diff_from_neutral = base_ph - 7.0
                ph_compensation = 0.003 * temp_diff * ph_diff_from_neutral
                calibrated_data['ph_calibrated'] = base_ph - ph_compensation

                # EC Calibration (temp compensation + formula + 2-point)
                temp_coeff = 1.0 + 0.02 * temp_diff
                compensated_ec_voltage = smoothed_raw_data['ec_voltage'] / temp_coeff if temp_coeff != 0 else 0
                v = compensated_ec_voltage
                base_ec = (133.42 * math.pow(v, 3)) - (255.86 * math.pow(v, 2)) + (857.39 * v)
                calibrated_data['ec_calibrated'] = (base_ec * settings.ec_slope) + settings.ec_intercept

                # Return original raw data and the final calibrated data
                return {**raw_data, **calibrated_data}
            
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

        try:
            arduino_ser = serial.Serial(ARDUINO_PORT, BAUDRATE, timeout=1)
            time.sleep(2)
            arduino_ser.reset_input_buffer()
            self.stdout.write(self.style.SUCCESS(f"Success: Connected to Arduino on {ARDUINO_PORT}."))
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

        self.stdout.write(self.style.SUCCESS("\nStarting data reception. Press Ctrl+C to exit."))

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
                        
                        # Create a new SensorData object with all available data
                        SensorData.objects.create(
                            air_temperature=all_data.get('air_temperature'),
                            air_humidity=all_data.get('air_humidity'),
                            co2=all_data.get('co2'),
                            insolation=all_data.get('insolation'),
                            water_temperature=all_data.get('water_temperature'),
                            weight_raw=all_data.get('weight_raw'),
                            weight_calibrated=all_data.get('weight_calibrated'),
                            ph_voltage=all_data.get('ph_voltage'),
                            ph_calibrated=all_data.get('ph_calibrated'),
                            ec_voltage=all_data.get('ec_voltage'),
                            ec_calibrated=all_data.get('ec_calibrated'),
                            soil_temperature=all_data.get('soil_temperature'),
                            soil_humidity=all_data.get('soil_humidity'),
                            soil_conductivity=all_data.get('soil_conductivity'),
                            soil_ph=all_data.get('soil_ph'),
                        )
                        self.stdout.write(self.style.SUCCESS(f"Saved smoothed data at {time.strftime('%H:%M:%S')}"))

                time.sleep(1)

            except KeyboardInterrupt:
                self.stdout.write(self.style.SUCCESS("\nExiting."))
                break
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"An unexpected error occurred in the main loop: {e}"))
                time.sleep(5)
        
        if arduino_ser.is_open:
            arduino_ser.close()
            self.stdout.write(self.style.SUCCESS("Arduino serial port closed."))

