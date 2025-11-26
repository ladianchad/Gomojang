import os
import json
import datetime

BASE_DIR_GOMOJANG = os.path.expanduser("~/gomojang/omnitor") 
CONFIG_FILE_PATH = os.path.join(BASE_DIR_GOMOJANG, "camera_config.json")
DEFAULT_CAPTURE_TIME = "12:00"

IMAGE_FILES_DIRECTORY = os.path.join(BASE_DIR_GOMOJANG, "omnitor/static/journal_images/")

def get_current_capture_time():
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            time_str = config.get('capture_time', DEFAULT_CAPTURE_TIME)
            datetime.strptime(time_str, '%H:%M')
            return time_str
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return DEFAULT_CAPTURE_TIME

def capture():
    pass