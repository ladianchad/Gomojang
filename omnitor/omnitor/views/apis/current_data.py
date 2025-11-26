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

def latest_data_api(request):
    try:
        latest = SensorData.objects.latest('timestamp')
        
        prev = SensorData.objects.filter(timestamp__lt=latest.timestamp).order_by('-timestamp').first()
        
        # 급수량 계산 (현재 무게 - 이전 무게)
        # 0보다 클 때만 급수량으로 인정 (무게가 줄어드는 건 증발/배액이므로 제외)
        irrigation_amount = 0
        if prev and latest.weight_calibrated is not None and prev.weight_calibrated is not None:
            diff = latest.weight_calibrated - prev.weight_calibrated
            if diff > 0:
                irrigation_amount = diff
        
        data = {
            'timestamp': latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'air_temperature': latest.air_temperature,
            'air_humidity': latest.air_humidity,
            'co2': latest.co2,
            'insolation': latest.insolation,
            'water_temperature': latest.water_temperature,
            'tip_total': latest.tip_total,
            'irrigation_amount': irrigation_amount,
            'weight_calibrated': latest.weight_calibrated,
            'ph_calibrated': latest.ph_calibrated,
            'ec_calibrated': latest.ec_calibrated,
            'soil_temperature': latest.soil_temperature,
            'soil_humidity': latest.soil_humidity,
            'soil_conductivity': latest.soil_conductivity,
            'soil_ph': latest.soil_ph,
        }
        return JsonResponse(data)
    except SensorData.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '데이터가 없습니다.'}, status=404)
    except Exception as e:
        print(f"Error in latest_data_api: {e}")
        return JsonResponse({'status': 'error', 'message': '서버 에러!!!'}, status=500)