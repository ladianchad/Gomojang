from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.templatetags.static import static
from datetime import timedelta, datetime
from .models import SensorData, CalibrationSettings, FarmJournal
import json
import serial
import time
import statistics
import os

# --- Configuration ---
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

# --- Helper Function for Calibration ---
def _get_stable_reading_from_arduino(data_index):
    """
    Connects to Arduino, reads several lines, and returns a stable median
    for a specific data point index in the CSV stream.
    """
    values = []
    # Using 'with' ensures the serial port is closed even if errors occur.
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            time.sleep(2) # Wait for connection to establish and initial data to clear.
            ser.flushInput()
            
            start_time = time.time()
            # Try to collect up to 15 samples within a 5-second window.
            while len(values) < 15 and (time.time() - start_time) < 5:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        parts = line.split(',')
                        if len(parts) == 7:
                            raw_value = float(parts[data_index])
                            values.append(raw_value)
                    except (UnicodeDecodeError, ValueError, IndexError):
                        # Silently ignore malformed lines and try again.
                        continue
            
            # We need at least 2 valid readings to be confident.
            if len(values) >= 2:
                # Median is more robust against outliers than mean.
                return statistics.median(values)
            else:
                # Not enough data was received in time.
                return f"Error: Not enough valid data received. Got {len(values)} samples."

    except serial.SerialException:
        return "Error: Could not open serial port. Check connection and permissions."
    except Exception as e:
        return f"Error: An unexpected error occurred: {e}"
    
    # --- API Views ---

@ensure_csrf_cookie
def settings_api(request):
    """API to get or save calibration settings."""
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
        }
        return JsonResponse(data)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Update only the fields that are present in the request
            for key, value in data.items():
                if hasattr(settings, key) and value is not None:
                    setattr(settings, key, float(value))
            settings.save()
            return JsonResponse({'status': 'success', 'message': 'Settings saved!'})
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return HttpResponseBadRequest(f"Invalid data format: {e}")

@ensure_csrf_cookie
def calibration_api(request):
    """Handles live requests for calibration actions."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST requests are allowed.")

    try:
        data = json.loads(request.body)
        action = data.get('action')
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    if action == 'tare':
        # Weight raw data is at index 4
        reading = _get_stable_reading_from_arduino(4)
        if isinstance(reading, float):
            return JsonResponse({'status': 'success', 'offset': reading})
        else:
            return JsonResponse({'status': 'error', 'message': reading}, status=500)

    elif action == 'get_ph_voltage':
        # pH voltage is at index 5
        reading = _get_stable_reading_from_arduino(5)
        if isinstance(reading, float):
            return JsonResponse({'status': 'success', 'voltage': reading})
        else:
            return JsonResponse({'status': 'error', 'message': reading}, status=500)

    return HttpResponseBadRequest("Invalid action specified.")
# --- Main Application Views ---

@ensure_csrf_cookie
def sensor_dashboard_view(request):
    """Renders the main single-page application dashboard."""
    return render(request, 'imojang/serial_display.html')

def latest_data_api(request):
    """API endpoint to return the latest sensor data as JSON."""
    try:
        latest = SensorData.objects.latest('timestamp')
        data = {
            'timestamp': latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'air_temperature': latest.air_temperature,
            'air_humidity': latest.air_humidity,
            'co2': latest.co2,
            'lux': latest.lux,
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
    """API endpoint to return recent data points for graphs."""
    timespan = request.GET.get('timespan', '1h') # Default to 1 hour
    
    end_time = timezone.now()
    if timespan == '10m':
        start_time = end_time - timedelta(minutes=10)
    elif timespan == '1h':
        start_time = end_time - timedelta(hours=1)
    elif timespan == '24h':
        start_time = end_time - timedelta(hours=24)
    elif timespan == '7d':
        start_time = end_time - timedelta(days=7)
    else: # Default
        start_time = end_time - timedelta(hours=1)
        
    data_points = SensorData.objects.filter(timestamp__range=(start_time, end_time)).order_by('timestamp')

    count = data_points.count()
    if count > 500:
        data_points = data_points[::count//500]

    data = {
        'labels': [d.timestamp.strftime('%H:%M') for d in data_points],
        'datasets': {
            'weight': [d.weight_calibrated for d in data_points],
            'air_temperature': [d.air_temperature for d in data_points],
            'air_humidity': [d.air_humidity for d in data_points],
            'co2': [d.co2 for d in data_points],
            'lux': [d.lux for d in data_points],
            'ec': [d.ec_calibrated for d in data_points],
            'ph': [d.ph_calibrated for d in data_points],
            'soil_temperature': [d.soil_temperature for d in data_points],
            'soil_humidity': [d.soil_humidity for d in data_points],
            'soil_conductivity': [d.soil_conductivity for d in data_points],
            'soil_ph': [d.soil_ph for d in data_points],
        }
    }
    return JsonResponse(data)
@ensure_csrf_cookie
def journal_api(request):
    if request.method == 'GET':
        date_str = request.GET.get('date')
        if not date_str:
            return HttpResponseBadRequest("Date parameter is required.")
        
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            journal_entry = FarmJournal.objects.get(date=selected_date)
            
            image_url = static(f'imojang/journal_images/{date_str}.jpg')

            data = {
                'status': 'found',
                'date': journal_entry.date.strftime('%Y-%m-%d'),
                'farm_work': journal_entry.farm_work,
                'pesticide': journal_entry.pesticide,
                'fertilizer': journal_entry.fertilizer,
                'harvest': journal_entry.harvest,
                'notes': journal_entry.notes,
                'image_url': image_url
            }
        except FarmJournal.DoesNotExist:
            image_url = static(f'imojang/journal_images/{date_str}.jpg')
            data = {'status': 'not_found', 'image_url': image_url}
        
        return JsonResponse(data)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            if not date_str:
                return HttpResponseBadRequest("Date is required.")
            
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            journal_entry, created = FarmJournal.objects.update_or_create(
                date=selected_date,
                defaults={
                    'farm_work': data.get('farm_work', ''),
                    'pesticide': data.get('pesticide', ''),
                    'fertilizer': data.get('fertilizer', ''),
                    'harvest': data.get('harvest', ''),
                    'notes': data.get('notes', ''),
                }
            )
            return JsonResponse({'status': 'success', 'message': '?쇱?媛 ??λ릺?덉뒿?덈떎.'})
        except (json.JSONDecodeError, ValueError) as e:
            return HttpResponseBadRequest(f"Invalid data: {e}")
        
    return HttpResponseBadRequest("Unsupported request method.")
