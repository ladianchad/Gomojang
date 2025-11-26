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
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    timespan = request.GET.get('timespan', None)
    end_time = timezone.now()
    start_time = None

    try:
        if start_date_str and end_date_str:
            start_time = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_dt_naive = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1, microseconds=-1)
            end_time = timezone.make_aware(end_dt_naive)
            print(f"Date range selected: {start_time} to {end_time}")
        elif timespan:
            if timespan == '10m': start_time = end_time - timedelta(minutes=10)
            elif timespan == '1h': start_time = end_time - timedelta(hours=1)
            elif timespan == '24h': start_time = end_time - timedelta(hours=24)
            elif timespan == '7d': start_time = end_time - timedelta(days=7)
            else: start_time = end_time - timedelta(hours=1); print(f"Warning: Invalid timespan, defaulting to 1h.")
            print(f"Timespan selected: {timespan}, range: {start_time} to {end_time}")
        else:
            start_time = end_time - timedelta(hours=1)
            print(f"시간 범위를 선택하지 않아 기본인 최근 1시간 단위로 표시합니다.")
    except ValueError:
        return JsonResponse({'status': 'error', 'message': '날짜 형식이 틀렸습니다. 연연연연-월월-일일 형식을 사용하세요.'}, status=400)
    except Exception as e:
        print(f"Error parsing date/time parameters: {e}")
        return JsonResponse({'status': 'error', 'message': '날짜 에러.'}, status=500)

    if start_time is None:
        return JsonResponse({'status': 'error', 'message': '시간 범위를 받지 못했습니다'}, status=400)
    try:
        data_points_qs = SensorData.objects.filter(timestamp__range=(start_time, end_time)).order_by('timestamp')
        count = data_points_qs.count()
        print(f"{count}개의 데이터를 찾았습니다.") # 디버깅용

        MAX_GRAPH_POINTS = 500
        data_points = []
        if count > MAX_GRAPH_POINTS:
            step = max(1, count // MAX_GRAPH_POINTS)
            data_points = list(data_points_qs[::step])
            print(f"Thinned data from {count} to {len(data_points)} points (step={step})")
        elif count > 0:
            data_points = list(data_points_qs)

        # 급수량 계산 로직 (그래프용)
        # 리스트를 순회하며 (현재 무게 - 이전 무게)가 양수일 때만 급수량으로 기록
        irrigation_list = []
        prev_weight = None
        
        for dp in data_points:
            current_weight = dp.weight_calibrated
            val = 0
            if current_weight is not None and prev_weight is not None:
                diff = current_weight - prev_weight
                if diff > 0:
                    val = diff
            irrigation_list.append(val)
            # 값이 None이 아닐 때만 prev_weight 갱신
            if current_weight is not None:
                prev_weight = current_weight
                
    except Exception as e:
        print(f"Error querying or thinning database: {e}")
        return JsonResponse({'status': 'error', 'message': 'Error retrieving data from database.'}, status=500)
    data = {
        'labels': [dp.timestamp.isoformat() for dp in data_points],
        'datasets': {
            'weight': [dp.weight_calibrated if dp.weight_calibrated is not None else None for dp in data_points],
            'irrigation': irrigation_list,
            'tip_total': [dp.tip_total if dp.tip_total is not None else None for dp in data_points],
            
            'air_temperature': [dp.air_temperature if dp.air_temperature is not None else None for dp in data_points],
            'air_humidity': [dp.air_humidity if dp.air_humidity is not None else None for dp in data_points],
            'co2': [dp.co2 if dp.co2 is not None else None for dp in data_points],
            'insolation': [dp.insolation if dp.insolation is not None else None for dp in data_points],
            
            'ec': [dp.ec_calibrated if dp.ec_calibrated is not None else None for dp in data_points],
            'ph': [dp.ph_calibrated if dp.ph_calibrated is not None else None for dp in data_points],
            'water_temperature': [dp.water_temperature if dp.water_temperature is not None else None for dp in data_points],

            'soil_temperature': [dp.soil_temperature if dp.soil_temperature is not None else None for dp in data_points],
            'soil_humidity': [dp.soil_humidity if dp.soil_humidity is not None else None for dp in data_points],
            'soil_conductivity': [dp.soil_conductivity if dp.soil_conductivity is not None else None for dp in data_points],
            'soil_ph': [dp.soil_ph if dp.soil_ph is not None else None for dp in data_points],
        }
    }
    return JsonResponse(data)