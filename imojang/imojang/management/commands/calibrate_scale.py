import serial
import time
import statistics
import json
from django.core.management.base import BaseCommand

# --- Configuration ---
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

class Command(BaseCommand):
    help = 'Performs interactive calibration for the load cell scale.'

    def __init__(self):
        super().__init__()
        self.ser = None
        self.OFFSET = 0
        self.SCALE = 1.0

    def get_stable_reading(self, samples=25):
        """Gets a stable reading from the 4th value of the CSV."""
        values = []
        self.ser.flushInput()
        self.stdout.write("Reading stable value...")
        while len(values) < samples:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    parts = line.split(',')
                    if len(parts) == 4:
                        raw_value = int(parts[3])
                        values.append(raw_value)
                except (UnicodeDecodeError, ValueError, IndexError):
                    pass # Ignore malformed lines
        
        if not values:
            self.stdout.write(self.style.ERROR("Could not read any valid data from the sensor."))
            return None
            
        mean_value = statistics.mean(values)
        self.stdout.write(f" Stable raw value is: {mean_value:.0f}")
        return mean_value

    def tare(self):
        """Tares the scale to set the zero point."""
        self.stdout.write(self.style.SUCCESS("\n--- Taring ---"))
        self.stdout.write("Please remove any weight from the scale and press Enter.")
        input()
        offset_val = self.get_stable_reading()
        if offset_val is not None:
            self.OFFSET = offset_val
            self.stdout.write(self.style.SUCCESS(f"Tare complete. Offset is now: {self.OFFSET:.0f}"))

    def calibrate(self):
        """Calibrates the scale using a known weight."""
        self.stdout.write(self.style.SUCCESS("\n--- Calibrating ---"))
        try:
            known_weight_g = float(input("Enter a known weight in grams (e.g., 100): "))
        except ValueError:
            self.stdout.write(self.style.ERROR("Invalid input. Please enter a number."))
            return

        self.stdout.write(f"Please place {known_weight_g}g on the scale and press Enter.")
        input()
        
        reading = self.get_stable_reading()
        if reading is None:
            return

        raw_value_of_weight = reading - self.OFFSET
        
        if known_weight_g == 0:
            self.stdout.write(self.style.ERROR("Error: Cannot calibrate with 0g."))
            return
        
        self.SCALE = raw_value_of_weight / known_weight_g
        
        if self.SCALE == 0:
            self.stdout.write(self.style.ERROR("Error: Scale factor is 0. Calibration failed."))
            return

        self.stdout.write(self.style.SUCCESS(f"Calibration complete. Scale factor is: {self.SCALE:.4f}"))

    def handle(self, *args, **kwargs):
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
            time.sleep(2) # Wait for the serial connection to initialize
            self.stdout.write(self.style.SUCCESS(f"Connected to {SERIAL_PORT}."))
        except serial.SerialException as e:
            self.stdout.write(self.style.ERROR(f"Error: Could not connect to {SERIAL_PORT}. {e}"))
            return

        self.tare()
        self.calibrate()

        calibration_data = {
            'offset': self.OFFSET,
            'scale': self.SCALE
        }
        
        with open('calibration.json', 'w') as f:
            json.dump(calibration_data, f, indent=4)
        
        self.stdout.write(self.style.SUCCESS("\nCalibration data saved to calibration.json!"))
        
        if self.ser and self.ser.is_open:
            self.ser.close()
