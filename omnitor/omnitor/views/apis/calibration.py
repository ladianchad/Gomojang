import json
import os

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import path

BASE_DIR_GOMOJANG = os.path.expanduser("~/gomojang/omnitor") 
CONFIG_FILE_PATH = os.path.join(BASE_DIR_GOMOJANG, "camera_config.json")


def api_setting(request):
    handlers = {
        "POST": post_handler,
    }

    handler = handlers.get(request.method)
    if handler is None:
        return HttpResponseBadRequest("Only POST requests are allowed.")

    return handler(request)

api_path = path('calibration_api/', api_setting, name='calibration_api')


def post_handler(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    reading, message = (None, "Invalid action")

    if action == 'get_weight_raw':
        reading, message = get_reading_from_sensor_file('weight_raw')
        if reading is not None:
            return JsonResponse({'status': 'success', 'raw': reading})

    elif action == 'get_ph_voltage':
        reading, message = get_reading_from_sensor_file('ph_voltage')
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    elif action == 'get_ec_voltage':
        reading, message = get_reading_from_sensor_file('ec_voltage')
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    if reading is None:
        detailed_message = f"Could not get stable reading: {message}"
        return JsonResponse({'status': 'error', 'message': detailed_message}, status=500)

    return HttpResponseBadRequest("Invalid action specified or failed to execute.")



