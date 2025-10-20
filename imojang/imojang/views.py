from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
# --- MODIFIED: Add FarmJournal to the import list ---
from .models import SensorData, CalibrationSettings, FarmJournal
import json
import serial
import time
import statistics

SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

def get_stable_reading_from_arduino(data_index):
    """
    Connects to Arduino and gets a stable reading for a specific data index.
    NEW Format: "AirT,AirH,CO2,insolation,Weight,pH_V,EC_V,WaterT"
    Indices:       0    1    2   3    4      5    6     7
    """
    values = []
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            time.sleep(2)
            ser.flushInput()
            
            sample_count = 0
            start_time = time.time()
            
            while sample_count < 15 and (time.time() - start_time) < 5:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        parts = line.split(',')
                        if len(parts) == 8: # <-- IMPORTANT: Check for 8 parts
                            raw_value = float(parts[data_index])
                            values.append(raw_value)
                            sample_count += 1
                    except (UnicodeDecodeError, ValueError, IndexError):
                        continue
            
            if len(values) < 2:
                return (None, f"Not enough valid data received. Got {len(values)} samples.")
            
            # Use median to avoid outliers
            return (statistics.median(values), "Success")

    except serial.SerialException as e:
        return (None, f"Serial port error: {e}")
    except Exception as e:
        return (None, f"An unexpected error occurred: {e}")

def settings_api(request):
    """API to get or save all calibration settings."""
    settings = CalibrationSettings.load()
    
    if request.method == 'GET':
        data = {
            'weight_offset': settings.weight_offset,
            'weight_scale': settings.weight_scale,
            'ph_point1_voltage': settings.ph_point1_voltage,
            'ph_point1_value': settings.ph_point1_value,
            'ph_point2_voltage': settings.ph_point2_voltage,
            'ph_point2_value': settings.ph_point2_value,
            'ph_slope': settings.ph_slope,
            'ph_intercept': settings.ph_intercept,
            # Add new EC fields
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
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, float(value))
            settings.save()
            return JsonResponse({'status': 'success', 'message': 'Settings saved!'})
        except Exception as e:
            return HttpResponseBadRequest(f"Invalid data: {e}")

def calibration_api(request):
    """Handles live requests for calibration actions."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST is allowed.")

    try:
        data = json.loads(request.body)
        action = data.get('action')
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    reading, message = (None, "Invalid action")

    if action == 'tare':
        reading, message = get_stable_reading_from_arduino(4) # Weight is at index 4
        if reading is not None:
            return JsonResponse({'status': 'success', 'offset': reading})
            
    elif action == 'get_ph_voltage':
        reading, message = get_stable_reading_from_arduino(5) # pH Voltage is at index 5
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    elif action == 'get_ec_voltage': # New action for EC
        reading, message = get_stable_reading_from_arduino(6) # EC Voltage is at index 6
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    if reading is None:
        return JsonResponse({'status': 'error', 'message': message}, status=500)

    return HttpResponseBadRequest("Invalid action specified.")

def sensor_dashboard_view(request):
    return render(request, 'imojang/serial_display.html')
def latest_data_api(request):
    try:
        latest = SensorData.objects.latest('timestamp')
        data = {
            'timestamp': latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'air_temperature': latest.air_temperature,
            'air_humidity': latest.air_humidity,
            'co2': latest.co2,
            'insolation': latest.insolation,
            'water_temperature': latest.water_temperature, # Add water temp
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
        return JsonResponse({'status': 'error', 'message': 'No data available.'}, status=404)

def historical_data_api(request):
    timespan = request.GET.get('timespan', '1h')
    end_time = timezone.now()
    if timespan == '10m': start_time = end_time - timedelta(minutes=10)
    elif timespan == '1h': start_time = end_time - timedelta(hours=1)
    elif timespan == '24h': start_time = end_time - timedelta(hours=24)
    elif timespan == '7d': start_time = end_time - timedelta(days=7)
    else: start_time = end_time - timedelta(hours=1)
        
    qs = SensorData.objects.filter(timestamp__range=(start_time, end_time)).order_by('timestamp')
    count = qs.count()
    if count > 500: qs = qs[::count//500]
    data = {
        'labels': [d.timestamp.strftime('%H:%M') for d in qs],
        'datasets': {
            'weight': [d.weight_calibrated for d in qs],
            'air_temperature': [d.air_temperature for d in qs],
            'air_humidity': [d.air_humidity for d in qs],
            'co2': [d.co2 for d in qs],
            'insolation': [d.insolation for d in qs],
            'ec': [d.ec_calibrated for d in qs],
            'ph': [d.ph_calibrated for d in qs],
            'water_temperature': [d.water_temperature for d in qs], # Add water temp
            'soil_temperature': [d.soil_temperature for d in qs],
            'soil_humidity': [d.soil_humidity for d in qs],
            'soil_conductivity': [d.soil_conductivity for d in qs],
            'soil_ph': [d.soil_ph for d in qs],
        }
    }
    return JsonResponse(data)

def journal_api(request):
    if request.method == 'GET':
        date_str = request.GET.get('date')
        if not date_str: return HttpResponseBadRequest("Date parameter is required.")
        
        image_url = f"/static/imojang/journal_images/{date_str}.jpg"
        
        try:
            entry = FarmJournal.objects.get(date=date_str)
            return JsonResponse({
                'status': 'found',
                'farm_work': entry.farm_work, 'pesticide': entry.pesticide,
                'fertilizer': entry.fertilizer, 'harvest': entry.harvest,
                'notes': entry.notes, 'image_url': image_url,
            })
        except FarmJournal.DoesNotExist:
            return JsonResponse({'status': 'not_found', 'image_url': image_url})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date = data.pop('date')
            entry, created = FarmJournal.objects.update_or_create(date=date, defaults=data)
            message = "Journal entry saved successfully!"
            if created: message = "Journal entry created successfully!"
            return JsonResponse({'status': 'success', 'message': message})
        except Exception as e:
            return HttpResponseBadRequest(f"Error saving journal: {e}")

