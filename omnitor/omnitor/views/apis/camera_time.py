import datetime
import json
import os

from django.http import JsonResponse, HttpResponseBadRequest, HttpRequest
from django.contrib.staticfiles.storage import staticfiles_storage

from django.urls import path

from omnitor.services import image_logging
from omnitor.views.utils import json_body_guard


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

@json_body_guard
def post_handler(request):
    data = json.loads(request.body)
    new_time = data.get('capture_time') # e.g., "14:30"
    image_logging.update_iamge_logging(new_time)
    return JsonResponse({'status': 'success', 'message': f'캡처 시간이 {new_time}으로 저장되었습니다.'})