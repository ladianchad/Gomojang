import os
import cv2
from datetime import datetime
import schedule
import time

# --- Settings ---
SAVE_DIRECTORY = "/home/$USER/gomojang/omnitor/omnitor/static/journal_images/"
IMAGE_WIDTH = 8000  # Using a more standard resolution like 1080p is often more stable
IMAGE_HEIGHT = 6000
CAPTURE_TIME = "12:00"
# --- NEW: Number of frames to discard for auto-exposure to settle ---
WARM_UP_FRAMES = 30

def decode_fourcc(val):
    """Decodes the FourCC integer value back to a string."""
    return "".join([chr((int(val) >> 8 * i) & 0xFF) for i in range(4)])

def take_picture_job():
    """Takes a picture after allowing the camera's auto-exposure to adjust."""
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

        # --- Set MJPG Format and Resolution ---
        # Note: Setting an extremely high resolution like 8000x6000 may not be supported
        # and can cause instability. 1920x1080 is a safer default.
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)
        
        # --- Verification ---
        actual_fourcc = decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"-> Requested Format: MJPG, Actual Format: {actual_fourcc}")
        print(f"-> Requested Resolution: {IMAGE_WIDTH}x{IMAGE_HEIGHT}, Actual Resolution: {actual_width}x{actual_height}")
        
        # --- MODIFICATION: Camera Warm-up ---
        # Instead of a long sleep, read and discard frames to allow auto-exposure to work.
        print(f"Warming up camera for {WARM_UP_FRAMES} frames...")
        for _ in range(WARM_UP_FRAMES):
            cap.read()
        print("Warm-up complete. Capturing final image.")
        # ------------------------------------

        # Read the final, properly exposed frame
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

def main():
    """Sets up and runs the scheduler."""
    print("--- Daily Picture Scheduler Started ---")
    print(f"A picture will be taken every day at {CAPTURE_TIME}.")
    
    schedule.every().day.at(CAPTURE_TIME).do(take_picture_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()

