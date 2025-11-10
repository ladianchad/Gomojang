import serial
import time
import csv
import datetime
from collections import deque # Used for the moving average filter

# -----------------------------------------------------------------
# 1. Settings
# -----------------------------------------------------------------

SERIAL_PORT = 'COM7'
BAUD_RATE = 9600           

# File and Sampling Settings
BASE_CSV_FILENAME = 'loadcell_test2'
TOTAL_SAMPLES = 100                 # Number of samples to collect per test
SAMPLE_INTERVAL = 2                 # Sample collection interval (seconds)

# Moving average filter window size
MVG_AVG_WINDOW_SIZE = 5

TEST_SUFFIXES = ['_none', '_pot', '_100g', '_200g']

# -----------------------------------------------------------------
# 2. Calibration Function
# -----------------------------------------------------------------

def get_stable_reading(ser, num_readings=10):
    """
    Reads multiple times and returns a stable average raw value.
    """
    readings = []
    print(f"Taking {num_readings} readings for stabilization...")
    
    # -----------------------------------------------------------------
    # *** THIS IS THE FIX (Good Practice) ***
    # Clear any old data from before the user pressed 'Enter'
    ser.reset_input_buffer()
    # -----------------------------------------------------------------
    
    while len(readings) < num_readings:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                readings.append(float(line))
                print(f"  -> Raw: {line}")
                time.sleep(0.1)
        except Exception as e:
            print(f"  -> Read error: {e}, skipping.")
            time.sleep(0.1)
            
    if not readings:
        raise Exception("Could not read serial data. Check connection.")
        
    return sum(readings) / len(readings)

def calibrate(ser):
    """
    Calculates the zero offset and scale.
    """
    print("--- Starting Load Cell Calibration ---")
    
    # 1. Calculate Zero Offset
    input("1. Remove all weight from the load cell. Press 'Enter' when ready...")
    zero_offset = get_stable_reading(ser)
    print(f"Zero Offset raw value: {zero_offset}\n")
    
    # 2. Calculate Scale
    while True:
        try:
            known_weight_str = input("2. Place a known weight (in grams) on the cell and enter the weight (e.g., 100): ")
            known_weight = float(known_weight_str)
            break
        except ValueError:
            print("Invalid input. Please enter numbers only.")
            
    input(f"3. The {known_weight}g weight is on the cell. Press 'Enter' to measure...")
    known_weight_reading = get_stable_reading(ser)
    print(f"{known_weight}g raw value: {known_weight_reading}\n")
    
    # Calculate scale: (KnownWeight) / (MeasuredRaw - ZeroOffset)
    scale = known_weight / (known_weight_reading - zero_offset)
    print(f"Scale value: {scale}")
    print("--- Calibration Complete ---\n")
    
    return zero_offset, scale

# -----------------------------------------------------------------
# 3. (New) Data Collection and Saving Function
# -----------------------------------------------------------------

def collect_data(ser, offset, scale, csv_filename, total_samples, sample_interval, mvg_avg_window_size):
    """
    Collects data for a specified duration, saves to CSV, and prints to terminal.
    """
    
    # Initialize deque for moving average filter
    mvg_avg_buffer = deque(maxlen=mvg_avg_window_size)
    
    print(f"\n--- Starting data collection for {csv_filename} ({total_samples} samples) ---")
    
    try:
        # Prepare CSV file
        with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write CSV header
            writer.writerow(['Timestamp', 'CalibratedValue_g', 'FilteredValue_g'])
            
            for i in range(total_samples):
                # 1. Receive raw load cell data via serial
                raw_value = None
                
                # -----------------------------------------------------------------
                # *** THIS IS THE FIX ***
                # Clear all old, stale data that piled up during time.sleep()
                ser.reset_input_buffer()
                # -----------------------------------------------------------------
                
                while raw_value is None:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            raw_value = float(line)
                        else:
                            # This will happen if readline times out (after 1 sec)
                            print("No data received, retrying...")
                    except Exception as e:
                        print(f"Data read error: {e}, retrying...")
                        time.sleep(0.1)

                # 2. Calibrate with offset and scale
                # ... (rest of your code is fine)
                calibrated_value = (raw_value - offset) * scale
                
                # 3. Apply moving average filter
                mvg_avg_buffer.append(calibrated_value)
                filtered_value = sum(mvg_avg_buffer) / len(mvg_avg_buffer)
                
                # 5. Save to CSV file with timestamp
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                data_to_write = [timestamp, calibrated_value, filtered_value]
                writer.writerow(data_to_write)
                
                # Print to terminal in real-time
                print(f"[{i+1}/{total_samples}] {timestamp} | "
                      f"Calibrated: {calibrated_value:10.2f}g | "
                      f"Filtered: {filtered_value:10.2f}g")
                
                # 4. Receive every (SAMPLE_INTERVAL) seconds
                time.sleep(sample_interval)
                
    except KeyboardInterrupt:
        print("\nCurrent test interrupted by user.")
        # Re-raise this exception to trigger the main 'finally' block
        raise 
    except Exception as e:
        print(f"\nError during data collection: {e}")

    print(f"--- {csv_filename} file saving complete ---\n")

# -----------------------------------------------------------------
# 4. (Modified) Main Execution Function
# -----------------------------------------------------------------

def main():
    ser = None # Declare outside 'try' to be accessible in 'finally'
    try:
        # Open serial port
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to serial port {SERIAL_PORT} at {BAUD_RATE} baud.")
        # Wait a moment for the connection to establish (e.g., Arduino reset)
        time.sleep(2) 
        
        # Run calibration once
        offset, scale = calibrate(ser)
        
        # Run the 4 tests sequentially
        for i, suffix in enumerate(TEST_SUFFIXES):
            # Combine file name (e.g., loadcell_test_none.csv)
            current_filename = f"{BASE_CSV_FILENAME}{suffix}.csv"
            
            print(f"=========================================")
            print(f"--- Preparing for Test {i+1} ({suffix}) ---")
            print(f"--- Place the object(s) for the '{suffix}' test on the cell. ---")
            print(f"=========================================")
            
            # Wait for user input
            input("Press 'Enter' when ready. (Ctrl+C to quit) ")
            
            # Call the data collection function
            collect_data(
                ser=ser,
                offset=offset,
                scale=scale,
                csv_filename=current_filename,
                total_samples=TOTAL_SAMPLES,
                sample_interval=SAMPLE_INTERVAL,
                mvg_avg_window_size=MVG_AVG_WINDOW_SIZE
            )

        print("--- All tests are complete. ---")

                
    except serial.SerialException as e:
        print(f"Error: Could not open serial port '{SERIAL_PORT}'.")
        print("  -> Check if the port name is correct and not in use by another program.")
        print("  -> (Linux/Mac) You might need to add permissions: 'sudo usermod -a -G dialout $USER'")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # Ensure the serial port is closed, even if an error occurs
        if ser and ser.is_open:
            ser.close()
            print("Serial port connection closed.")

# Run the script
if __name__ == "__main__":
    main()
