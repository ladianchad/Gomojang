import os
import cv2
from datetime import datetime
import schedule
import time
import json

# --- Directory and Time Settings ---
BASE_DIR = os.path.expanduser("~/gomojang/omnitor")
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "camera_config.json")
DEFAULT_CAPTURE_TIME = "12:00"
SAVE_DIRECTORY = os.path.join(BASE_DIR, "omnitor/static/journal_images/")

# --- Settings ---
IMAGE_WIDTH = 8000
IMAGE_HEIGHT = 6000
WARM_UP_FRAMES = 30

def decode_fourcc(val):
    return "".join([chr((int(val) >> 8 * i) & 0xFF) for i in range(4)])

def take_picture_job():
    print(f"[{datetime.now()}] Job triggered: Starting picture capture...")
    cap = None
    try:
        os.makedirs(SAVE_DIRECTORY, exist_ok=True)
        filename = f"{datetime.now().strftime('%Y-%m-%d')}.jpg"
        full_path = os.path.join(SAVE_DIRECTORY, filename)
        
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Cannot open camera. Check connection or other processes.")
            return
            
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
        
        actual_fourcc = decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"-> Requested Format: MJPG, Actual Format: {actual_fourcc}")
        print(f"-> Requested Resolution: {IMAGE_WIDTH}x{IMAGE_HEIGHT}, Actual Resolution: {actual_width}x{actual_height}")
        
        print(f"Warming up camera for {WARM_UP_FRAMES} frames...")
        for _ in range(WARM_UP_FRAMES):
            cap.read()
        print("Warm-up complete. Capturing final image.")

        ret, frame = cap.read()

        if ret:
            cv2.imwrite(full_path, frame)
            print(f"Success! Picture saved to: {full_path}")
        else:
            print("Error: Failed to capture final image from the camera.")

    except Exception as e:
        print(f"An unexpected error occurred during capture: {e}")
    finally:
        if cap is not None and cap.isOpened():
            cap.release()
            print("Camera resource has been released.")

def load_capture_time():
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            time_str = config.get('capture_time', DEFAULT_CAPTURE_TIME)
            datetime.strptime(time_str, '%H:%M') 
            return time_str
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        print(f"Config file not found or invalid. Using default time: {DEFAULT_CAPTURE_TIME}")
        return DEFAULT_CAPTURE_TIME
    except Exception as e:
        print(f"Error loading config file: {e}. Using default.")
        return DEFAULT_CAPTURE_TIME

def main():
    print("--- Daily Picture Scheduler Started ---")
    
    current_capture_time = load_capture_time()
    print(f"Scheduling initial job for: {current_capture_time}")
    
    schedule.every().day.at(current_capture_time).do(take_picture_job).tag('daily-picture')
    
    while True:
        schedule.run_pending()
        
        time.sleep(60) 
        
        new_capture_time = load_capture_time()
        
        if new_capture_time != current_capture_time:
            print(f"[{datetime.now()}] Capture time change detected!")
            print(f"Updating schedule from {current_capture_time} to {new_capture_time}")
            
            schedule.clear('daily-picture')
            
            schedule.every().day.at(new_capture_time).do(take_picture_job).tag('daily-picture')
            
            current_capture_time = new_capture_time

if __name__ == "__main__":
    main()
