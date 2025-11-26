from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.staticfiles.storage import staticfiles_storage

from ..models.models import SensorData, CalibrationSettings, FarmJournal
import json
import time
import statistics
import math
import os

# 카메라 설정
BASE_DIR_GOMOJANG = os.path.expanduser("~/gomojang/omnitor") 
CONFIG_FILE_PATH = os.path.join(BASE_DIR_GOMOJANG, "camera_config.json")
DEFAULT_CAPTURE_TIME = "12:00"

IMAGE_FILES_DIRECTORY = os.path.join(BASE_DIR_GOMOJANG, "omnitor/static/journal_images/")

# 카메라 시간 조정
def get_current_capture_time():
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            time_str = config.get('capture_time', DEFAULT_CAPTURE_TIME)
            datetime.strptime(time_str, '%H:%M')
            return time_str
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return DEFAULT_CAPTURE_TIME


