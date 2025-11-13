from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings as django_settings
from django.contrib.staticfiles.storage import staticfiles_storage
from .models import SensorData, CalibrationSettings, FarmJournal
import json
import time
import statistics
import math
import os

# --- Camera Settings Path --
BASE_DIR_GOMOJANG = os.path.expanduser("~/gomojang/omnitor") 
CONFIG_FILE_PATH = os.path.join(BASE_DIR_GOMOJANG, "camera_config.json")
DEFAULT_CAPTURE_TIME = "12:00"

IMAGE_FILES_DIRECTORY = os.path.join(BASE_DIR_GOMOJANG, "omnitor/static/journal_images/")

# --- Helper Function for Camera Time ---
def get_current_capture_time():
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            time_str = config.get('capture_time', DEFAULT_CAPTURE_TIME)
            datetime.strptime(time_str, '%H:%M')
            return time_str
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return DEFAULT_CAPTURE_TIME

# --- Helper Function for Calibration ---
def get_reading_from_sensor_file(target_key):
    """
    target_key 예시: 'weight_raw', 'ph_voltage', 'ec_voltage'
    """
    # read_sensors.py가 저장하는 파일 위치
    state_file_path = '/tmp/sensor_state.json' 
    readings = []
    
    # 파일이 생성되거나 업데이트될 때까지 최대 3초간 시도
    start_time = time.time()
    
    while (time.time() - start_time) < 3:
        try:
            if os.path.exists(state_file_path):
                with open(state_file_path, 'r') as f:
                    data = json.load(f)
                    
                    # 요청한 키(예: 'weight_raw')가 있으면 리스트에 추가
                    if target_key in data:
                        readings.append(data[target_key])
            
            # 안정적인 값을 위해 5번 정도 읽으면 중앙값 반환
            if len(readings) >= 5:
                return (statistics.median(readings), "Success")
                
            time.sleep(0.1) # 0.1초 대기 (read_sensors가 0.1초마다 갱신하므로)
            
        except (json.JSONDecodeError, IOError):
            # 파일이 쓰기 중(Lock)이라 읽기 실패할 수 있음 -> 무시하고 재시도
            time.sleep(0.05)
        except Exception as e:
            print(f"Error reading state file: {e}")
            return (None, f"Error: {e}")

    if not readings:
        return (None, "Timeout: 센서 데이터 파일(/tmp/sensor_state.json)을 읽을 수 없습니다. read_sensors가 실행 중인가요?")
    
    # 5개를 못 채웠더라도 읽은 게 있으면 반환
    return (statistics.median(readings), "Success")
    
def settings_api(request):
    settings = CalibrationSettings.load()

    if request.method == 'GET':
        data = {
            'weight_point1_raw': settings.weight_point1_raw,
            'weight_point1_value': settings.weight_point1_value,
            'weight_point2_raw': settings.weight_point2_raw,
            'weight_point2_value': settings.weight_point2_value,
            'weight_slope': settings.weight_slope,
            'weight_intercept': settings.weight_intercept,
            
            'ph_point1_voltage': settings.ph_point1_voltage,
            'ph_point1_value': settings.ph_point1_value,
            'ph_point2_voltage': settings.ph_point2_voltage,
            'ph_point2_value': settings.ph_point2_value,
            'ph_slope': settings.ph_slope,
            'ph_intercept': settings.ph_intercept,
            
            'ec_point1_voltage': settings.ec_point1_voltage,
            'ec_point1_value': settings.ec_point1_value,
            'ec_point2_voltage': settings.ec_point2_voltage,
            'ec_point2_value': settings.ec_point2_value,
            'ec_slope': settings.ec_slope,
            'ec_intercept': settings.ec_intercept,
    }
        return JsonResponse(data)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            changed = False
            for key, value in data.items():
                if key.endswith('_voltage') or key.endswith('_value') or key.endswith('_raw') or key.endswith('_slope') or key.endswith('_intercept'):
                    try:
                        float_value = float(value) if value is not None and value != '' else None
                        if hasattr(settings, key) and getattr(settings, key) != float_value:
                            setattr(settings, key, float_value)
                            changed = True
                    except (ValueError, TypeError):
                        return HttpResponseBadRequest(f"Invalid numeric value for {key}: {value}")
                elif hasattr(settings, key):
                    if getattr(settings, key) != value:
                        setattr(settings, key, value)
                        changed = True

            if changed:
                settings.save()
                print("Saved calibration settings:", data)
                return JsonResponse({'status': 'success', 'message': 'Settings saved!'})
            else:
                return JsonResponse({'status': 'success', 'message': 'No changes detected.'})
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return HttpResponseBadRequest(f"Invalid data format: {e}")
        except Exception as e:
            print(f"Error saving settings: {e}")
            return JsonResponse({'status': 'error', 'message': 'Failed to save settings.'}, status=500)

def calibration_api(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST requests are allowed.")

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


def sensor_dashboard_view(request):
    return render(request, 'omnitor/index.html')

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

def historical_data_api(request):
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

        # [추가됨] 급수량 계산 로직 (그래프용)
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
            'tip_total': [getattr(dp, 'tip_total', 0) for dp in data_points],
            
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

def journal_api(request):
    if request.method == 'GET':
        date_str = request.GET.get('date')
        if not date_str: return HttpResponseBadRequest("Date parameter is required.")
        image_name = f"{date_str}.jpg"
        image_relative_path = os.path.join('omnitor', 'journal_images', image_name)
        image_url = staticfiles_storage.url(image_relative_path)
        image_capture_time_str = None
        try:
            full_image_path = os.path.join(IMAGE_FILES_DIRECTORY, image_name)
            if os.path.exists(full_image_path):
                mtime = os.path.getmtime(full_image_path)
                image_capture_time = datetime.fromtimestamp(mtime)
                image_capture_time_str = image_capture_time.strftime('%H:%M:%S')
        except Exception as e:
            print(f"Error getting image mtime for {date_str}: {e}")
        try:
            entry = FarmJournal.objects.get(date=date_str)
            return JsonResponse({
                'status': 'found',
                'farm_work': entry.farm_work,
                'pesticide': entry.pesticide,
                'fertilizer': entry.fertilizer,
                'harvest': entry.harvest,
                'notes': entry.notes,
                'image_url': image_url,
                'image_capture_time': image_capture_time_str
            })
        except FarmJournal.DoesNotExist:
            return JsonResponse({'status': 'not_found', 'image_url': image_url, 'image_capture_time': image_capture_time_str})
        except Exception as e:
            print(f"Error fetching journal entry for {date_str}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Failed to retrieve journal entry.'}, status=500)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.pop('date', None)
            if not date_str:
                return HttpResponseBadRequest("Date is required to save journal entry.")

            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

            allowed_fields = {'farm_work', 'pesticide', 'fertilizer', 'harvest', 'notes'}
            defaults_data = {k: v for k, v in data.items() if k in allowed_fields}

            entry, created = FarmJournal.objects.update_or_create(date=date_str, defaults=defaults_data)
            message = "Journal entry updated successfully!"
            if created: message = "Journal entry created successfully!"
            print(f"Saved journal for {date_str}: {defaults_data}")
            return JsonResponse({'status': 'success', 'message': message})
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON data.")
        except Exception as e:
            print(f"Error saving journal for {date_str}: {e}")
            # Provide a more generic error message to the user
            return JsonResponse({'status': 'error', 'message': 'Failed to save journal entry due to a server error.'}, status=500)

# --- Camera Time Setting API ---
def camera_time_api(request):
    if request.method == 'GET':
        current_time = get_current_capture_time()
        return JsonResponse({'status': 'success', 'capture_time': current_time})
    if request.method == 'POST':
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
    return HttpResponseBadRequest("지원하지 않는 메소드입니다.")
