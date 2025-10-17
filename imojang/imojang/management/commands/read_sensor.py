import os
import sys
import serial
import time
import math
import minimalmodbus
from django.core.management.base import BaseCommand

from imojang.models import SensorData, CalibrationSettings

ARDUINO_PORT = '/dev/ttyACM0'
BAUDRATE = 9600
MODBUS_PORT = '/dev/ttyUSB0'
MODBUS_ADDRESS = 1

class Command(BaseCommand):
    help = 'Reads data from Arduino and Modbus, applies calibration, and saves to the database.'

    def parse_arduino_data(self, serial_line, settings):
        """
        Parses a comma-separated line from Arduino and applies all calibrations.
        Format: "AirTemp,AirHum,CO2,Lux,Weight_Raw,pH_V,EC_V,WaterTemp"
        """
        try:
            parts = serial_line.strip().split(',')
            if len(parts) == 8:
                raw_data = {
                    'air_temperature': float(parts[0]),
                    'air_humidity': float(parts[1]),
                    'co2': float(parts[2]),
                    'lux': float(parts[3]),
                    'weight_raw': float(parts[4]),
                    'ph_voltage': float(parts[5]),
                    'ec_voltage': float(parts[6]),
                    'water_temperature': float(parts[7]),
                }

                calibrated_data = {}
                
                # Weight calibration
                calibrated_data['weight_calibrated'] = (raw_data['weight_raw'] - settings.weight_offset) / settings.weight_scale if settings.weight_scale != 0 else 0

                # pH Calibration (2-point + temperature compensation)
                base_ph = (raw_data['ph_voltage'] * settings.ph_slope) + settings.ph_intercept
                temp_diff = raw_data['water_temperature'] - 25.0
                ph_diff_from_neutral = base_ph - 7.0
                ph_compensation = 0.003 * temp_diff * ph_diff_from_neutral
                calibrated_data['ph_calibrated'] = base_ph - ph_compensation

                # --- EC Calibration (2-Step Process as you requested) ---
                
                # Step 1.1: Temperature Compensation for Voltage
                temp_coeff = 1.0 + 0.02 * (raw_data['water_temperature'] - 25.0)
                compensated_ec_voltage = raw_data['ec_voltage'] / temp_coeff if temp_coeff != 0 else 0
                
                # Step 1.2: Apply the polynomial formula to get a base EC value
                v = compensated_ec_voltage
                base_ec = (133.42 * math.pow(v, 3)) - (255.86 * math.pow(v, 2)) + (857.39 * v)
                
                # Step 2: Apply the final two-point linear calibration (from user)
                calibrated_data['ec_calibrated'] = (base_ec * settings.ec_slope) + settings.ec_intercept

                return {**raw_data, **calibrated_data}
            
            else:
                self.stdout.write(self.style.WARNING(f"Warning: Incorrect Arduino data format. (Received {len(parts)} items, expected 8)"))
                return None
        except (ValueError, IndexError) as e:
            self.stderr.write(self.style.ERROR(f"Error: Could not parse Arduino data - {e}"))
            return None
    def read_modbus_sensor(self, instrument):
        """Reads data from the Modbus soil sensor."""
        try:
            data = instrument.read_registers(0, 4, 3)
            return {
                'soil_humidity': data[0] / 10.0,
                'soil_temperature': data[1] / 10.0,
                'soil_conductivity': float(data[2]),
                'soil_ph': data[3] / 10.0
            }
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

        try:
            instrument = minimalmodbus.Instrument(MODBUS_PORT, MODBUS_ADDRESS, mode='rtu')
            instrument.serial.baudrate = 4800
            instrument.serial.timeout = 1
            instrument.close_port_after_each_call = True
            self.stdout.write(self.style.SUCCESS(f"Success: Modbus instrument configured for {MODBUS_PORT}."))
        except serial.SerialException as e:
            self.stderr.write(self.style.ERROR(f"Modbus connection failed: {e}. Soil data will be unavailable."))
            instrument = None

        self.stdout.write(self.style.SUCCESS("\nStarting data reception. Press Ctrl+C to exit."))

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
                        
                        SensorData.objects.create(**all_data)
                        self.stdout.write(self.style.SUCCESS(f"Saved data at {time.strftime('%H:%M:%S')}"))

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

