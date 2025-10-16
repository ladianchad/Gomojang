import serial
import time
import minimalmodbus
from django.core.management.base import BaseCommand
from imojang.models import SensorData, CalibrationSettings

# --- Hardware Settings ---
# Ensure these port names are correct for your Raspberry Pi setup
ARDUINO_PORT = '/dev/ttyACM0'
ARDUINO_BAUDRATE = 9600
MODBUS_PORT = '/dev/ttyUSB0'
MODBUS_BAUDRATE = 4800
MODBUS_ADDRESS = 1

class Command(BaseCommand):
    help = 'Continuously reads sensor data from Arduino and Modbus, calibrates it, and saves it to the database.'

    def handle(self, *args, **kwargs):
        """ The main entry point for the management command. """
        self.stdout.write(self.style.SUCCESS("Initializing sensor connections..."))

        # --- Initialize Connections ---
        arduino_ser = self.connect_arduino()
        modbus_instrument = self.connect_modbus()

        if not arduino_ser:
            self.stdout.write(self.style.ERROR("Could not connect to the Arduino. Please check the connection and port name. Exiting."))
            return
        
        if not modbus_instrument:
            self.stdout.write(self.style.WARNING("Could not connect to the Modbus sensor. Will proceed with Arduino data only."))


        self.stdout.write(self.style.SUCCESS("\nStarting data logging loop. Press Ctrl+C to exit."))

        try:
            while True:
                # --- Fetch latest calibration settings from DB ---
                settings = CalibrationSettings.load()

                # --- Read from sensors ---
                arduino_data = self.read_arduino(arduino_ser)
                soil_data = self.read_modbus(modbus_instrument)

                if arduino_data:
                    # --- Calibrate Data ---
                    calibrated_weight = self.calibrate_weight(arduino_data['weight_raw'], settings)
                    calibrated_ph = self.calibrate_ph(arduino_data['ph_voltage'], settings)

                    # --- Prepare data object for saving ---
                    data_to_save = {
                        'air_temperature': arduino_data['air_temperature'],
                        'air_humidity': arduino_data['air_humidity'],
                        'co2': arduino_data['co2'],
                        'lux': arduino_data['lux'],
                        'weight_raw': arduino_data['weight_raw'],
                        'weight_calibrated': calibrated_weight,
                        'ph_voltage': arduino_data['ph_voltage'],
                        'ph_calibrated': calibrated_ph,
                        'ec_raw': arduino_data['ec_raw'],
                        'ec_calibrated': arduino_data['ec_raw'], # Assuming 1:1 for now
                    }

                    if soil_data:
                        data_to_save.update(soil_data)
                    
                    # --- Save to Database ---
                    SensorData.objects.create(**data_to_save)
                    self.stdout.write(self.style.SUCCESS(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Data saved successfully."))
                
                else:
                    self.stdout.write(self.style.WARNING("Skipped saving due to invalid Arduino data."))

                time.sleep(5) # Wait 5 seconds before the next reading cycle

        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nLogging stopped by user."))
        finally:
            if arduino_ser and arduino_ser.is_open:
                arduino_ser.close()
                self.stdout.write("Arduino serial port closed.")

    def connect_arduino(self):
        """ Establishes and returns a connection to the Arduino. """
        try:
            ser = serial.Serial(ARDUINO_PORT, ARDUINO_BAUDRATE, timeout=2)
            time.sleep(2) # Wait for the connection to settle
            ser.reset_input_buffer()
            self.stdout.write(self.style.SUCCESS(f"Connected to Arduino on {ARDUINO_PORT}."))
            return ser
        except serial.SerialException as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to Arduino: {e}"))
            return None

    def connect_modbus(self):
        """ Configures and returns a connection to the Modbus sensor. """
        try:
            instrument = minimalmodbus.Instrument(MODBUS_PORT, MODBUS_ADDRESS, mode='rtu')
            instrument.serial.baudrate = MODBUS_BAUDRATE
            instrument.serial.bytesize = 8
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = 1
            instrument.serial.timeout = 1
            instrument.close_port_after_each_call = True
            self.stdout.write(self.style.SUCCESS(f"Modbus instrument configured for {MODBUS_PORT}."))
            return instrument
        except serial.SerialException as e:
            self.stdout.write(self.style.ERROR(f"Failed to configure Modbus sensor: {e}"))
            return None

    def read_arduino(self, ser):
        """ Reads and parses a single line of data from the Arduino. """
        if not ser or not ser.is_open:
            return None
        
        # Try to read a few times to get a valid line
        for _ in range(3):
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    parts = line.split(',')
                    if len(parts) == 7:
                        return {
                            'air_temperature': float(parts[0]),
                            'air_humidity': float(parts[1]),
                            'co2': int(parts[2]),
                            'lux': float(parts[3]),
                            'weight_raw': int(parts[4]),
                            'ph_voltage': float(parts[5]),
                            'ec_raw': float(parts[6])
                        }
                except (ValueError, IndexError, UnicodeDecodeError):
                    continue # Ignore this line and try the next
        return None
            
    def read_modbus(self, instrument):
        """ Reads and parses data from the Modbus soil sensor. """
        if not instrument: return None
        try:
            # Registers: Soil Hum, Soil Temp, Soil EC, Soil pH
            data = instrument.read_registers(0, 4, 3) 
            return {
                'soil_humidity': data[0] / 10.0,
                'soil_temperature': data[1] / 10.0,
                'soil_conductivity': data[2],
                'soil_ph': data[3] / 10.0
            }
        except Exception as e: # Catches Modbus exceptions
            self.stdout.write(self.style.WARNING(f"Could not read from Modbus sensor: {e}"))
            return None

    def calibrate_weight(self, raw_value, settings):
        """ Applies calibration formula to the raw weight reading. """
        if settings.weight_scale == 0: return raw_value # Avoid division by zero
        return (raw_value - settings.weight_offset) / settings.weight_scale

    def calibrate_ph(self, voltage, settings):
        """ Applies the calculated linear formula to the pH voltage. """
        return (settings.ph_slope * voltage) + settings.ph_intercept

