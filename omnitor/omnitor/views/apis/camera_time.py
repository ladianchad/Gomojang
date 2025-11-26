import datetime
import json
import os

from django.http import JsonResponse, HttpResponseBadRequest, HttpRequest
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
        new_time = data.get('capture_time') # e.g., "14:30"
        if not new_time:
            return HttpResponseBadRequest("JSON 본문에 'capture_time'이 없습니다.")
        try:
            datetime.strptime(new_time, '%H:%M')
        except ValueError:
                return HttpResponseBadRequest("잘못된 시간 형식입니다. HH:MM 형식을 사용하세요.")
        config_data = {'capture_time': new_time}
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config_data, f)
        print(f"Camera capture time updated to: {new_time}")
        return JsonResponse({'status': 'success', 'message': f'캡처 시간이 {new_time}으로 저장되었습니다.'})
    except json.JSONDecodeError:
        return HttpResponseBadRequest("잘못된 JSON 형식입니다.")
    except Exception as e:
        print(f"Error saving camera config: {e}")
        return JsonResponse({'status': 'error', 'message': '서버 오류로 시간 저장에 실패했습니다.'}, status=500)