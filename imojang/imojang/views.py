from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import timedelta
from .models import SensorData, CalibrationSettings
import json
import serial
import time
import statistics

# --- Configuration ---
# Match these with your read_sensors.py script and hardware setup
SERIAL_PORT = '/dev/ttyACM0'
BAUD_RATE = 9600

# --- Helper Function for Calibration ---
def get_stable_reading_from_arduino(data_index):
    """
    Connects to Arduino, reads several lines, and returns a stable average 
    for a specific data point index in the CSV stream.
    
    CSV Format: "Temp,Hum,CO2,Lux,Weight_Raw,pH_Voltage,EC_Raw"
    Indices:      0    1   2   3      4          5         6
    """
    values = []
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            time.sleep(2) # Wait for connection to establish
            ser.flushInput()
            
            # Read a number of samples to get a stable value
            sample_count = 0
            max_samples = 25
            start_time = time.time()
            
            while sample_count < max_samples and (time.time() - start_time) < 5: # 5-second timeout
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        parts = line.split(',')
                        if len(parts) == 7:
                            raw_value = float(parts[data_index])
                            values.append(raw_value)
                            sample_count += 1
                    except (UnicodeDecodeError, ValueError, IndexError):
                        continue # Ignore malformed lines
                time.sleep(0.05)

        if len(values) < 5: # Need at least a few values to be confident
            return None
        # Return the average of the last 5 readings for stability
        return statistics.mean(values[-5:])

    except serial.SerialException:
        return None


# --- API Views ---

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
                if hasattr(settings, key):
                    setattr(settings, key, float(value))
            settings.save()
            return JsonResponse({'status': 'success', 'message': 'Settings saved!'})
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return HttpResponseBadRequest(f"Invalid data format: {e}")

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
        reading = get_stable_reading_from_arduino(4)
        if reading is not None:
            return JsonResponse({'status': 'success', 'offset': reading})
        else:
            return JsonResponse({'status': 'error', 'message': 'Could not read from Arduino. Check connection.'}, status=500)

    elif action == 'get_ph_voltage':
        # pH voltage is at index 5
        reading = get_stable_reading_from_arduino(5)
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})
        else:
            return JsonResponse({'status': 'error', 'message': 'Could not read from Arduino. Check connection.'}, status=500)

    return HttpResponseBadRequest("Invalid action specified.")


# --- Main Application Views ---

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

    # To avoid sending too much data to the browser, we can thin it out if the dataset is large
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
            'ec': [d.ec_calibrated for d in data_points],
            'ph': [d.ph_calibrated for d in data_points],
            # --- ADDED SOIL DATA FOR GRAPHS ---
            'soil_temperature': [d.soil_temperature for d in data_points],
            'soil_humidity': [d.soil_humidity for d in data_points],
            'soil_conductivity': [d.soil_conductivity for d in data_points],
            'soil_ph': [d.soil_ph for d in data_points],
        }
    }
    return JsonResponse(data)

