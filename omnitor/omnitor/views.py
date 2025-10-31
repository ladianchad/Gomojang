from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings as django_settings
from django.contrib.staticfiles.storage import staticfiles_storage
from .models import SensorData, CalibrationSettings, FarmJournal # FarmJournal 추가
import json
import serial
import time
import statistics
import math
import os 

# --- Configuration ---
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600

# --- Helper Function for Calibration ---
def get_stable_reading_from_arduino(data_index):
    """
    Connects to Arduino, reads several lines, and returns a stable median value
    for a specific data point index in the CSV stream.
    CSV Format: "AirTemp,AirHum,CO2,Insolation,Weight_Raw,pH_V,EC_V,WaterTemp"
    Indices:       0       1     2       3          4         5    6      7
    """
    values = []
    ser = None # Initialize ser to None
    try:
        # Check if the serial port exists (basic check)
        if not os.path.exists(SERIAL_PORT):
             print(f"Error: Serial port {SERIAL_PORT} not found.")
             return (None, f"Serial port {SERIAL_PORT} not found.") # Return error message

        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1.5) # Slightly shorter timeout
        ser.flushInput() 
        
        sample_count = 0
        max_samples = 15 # Reduced sample count for faster response
        start_time = time.time()
        
        while sample_count < max_samples and (time.time() - start_time) < 5: # 5-second overall timeout
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    parts = line.split(',')
                    if len(parts) == 8: # Check for 8 parts
                        raw_value = float(parts[data_index])
                        values.append(raw_value)
                        sample_count += 1
                except (UnicodeDecodeError, ValueError, IndexError) as e:
                     print(f"Debug: Error parsing line '{line}': {e}")
                     continue 
            time.sleep(0.05) 

        if len(values) < 2: # Require at least 2 valid samples
            msg = f"Not enough valid data received. Got {len(values)} samples."
            print(f"Error: {msg}")
            return (None, msg) # Return error message
            
        # Return the median of the collected values
        return (statistics.median(values), "Success")

    except serial.SerialException as e:
        msg = f"Serial port error: {e}"
        print(f"Error: {msg}")
        return (None, msg) # Return error message
    except Exception as e:
        msg = f"An unexpected error occurred: {e}"
        print(f"Error: {msg}")
        return (None, msg) # Return error message
    finally:
        if ser and ser.is_open:
            ser.close()

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
            'ec_point1_voltage': settings.ec_point1_voltage,
            'ec_point1_value': settings.ec_point1_value,
            'ec_point2_voltage': settings.ec_point2_voltage,
            'ec_point2_value': settings.ec_point2_value,
            'ec_slope': settings.ec_slope,
            'ec_intercept': settings.ec_intercept,
  _}
        return JsonResponse(data)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            changed = False
            for key, value in data.items():
                if key.endswith('_voltage') or key.endswith('_value') or key.endswith('_offset') or key.endswith('_scale') or key.endswith('_slope') or key.endswith('_intercept'):
                    try:
                        # Handle potential None or empty string values gracefully
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
    """Handles live requests for calibration actions (Tare, Get Voltage)."""
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST requests are allowed.")

    try:
        data = json.loads(request.body)
        action = data.get('action')
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON.")

    reading, message = (None, "Invalid action")

    if action == 'tare':
        reading, message = get_stable_reading_from_arduino(4) 
        if reading is not None:
            return JsonResponse({'status': 'success', 'offset': reading})
            
    elif action == 'get_ph_voltage':
        reading, message = get_stable_reading_from_arduino(5) 
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    elif action == 'get_ec_voltage': 
        reading, message = get_stable_reading_from_arduino(6) 
        if reading is not None:
            return JsonResponse({'status': 'success', 'voltage': reading})

    # Centralized error handling if reading is None
    if reading is None:
         # Include the specific error message from the helper function
         detailed_message = f"Could not get stable reading: {message}"
         return JsonResponse({'status': 'error', 'message': detailed_message}, status=500)

    # If action was valid but reading failed somehow (shouldn't happen with current logic)
    return HttpResponseBadRequest("Invalid action specified or failed to execute.")

# --- Main Application Views ---

def sensor_dashboard_view(request):
    """Renders the main single-page application dashboard."""
    return render(request, 'omnitor/index.html')

def latest_data_api(request):
    """API endpoint to return the latest sensor data as JSON."""
    try:
        latest = SensorData.objects.latest('timestamp')
        data = {
            'timestamp': latest.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'air_temperature': latest.air_temperature,
            'air_humidity': latest.air_humidity,
            'co2': latest.co2,
            'insolation': latest.insolation, 
            'water_temperature': latest.water_temperature, 
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
    except Exception as e:
        print(f"Error in latest_data_api: {e}")
        return JsonResponse({'status': 'error', 'message': 'Server error fetching latest data.'}, status=500)
    
def historical_data_api(request):
    """API endpoint to return recent data points for graphs, supporting both timespan and date range."""
    
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
            print(f"Warning: No time range specified, defaulting to last 1 hour.")
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)
    except Exception as e:
         print(f"Error parsing date/time parameters: {e}")
         return JsonResponse({'status': 'error', 'message': 'Error processing date/time parameters.'}, status=500)

    if start_time is None:
         return JsonResponse({'status': 'error', 'message': 'Could not determine time range.'}, status=400)
    
    # --- Query Database ---
    try:
        data_points_qs = SensorData.objects.filter(timestamp__range=(start_time, end_time)).order_by('timestamp')
        count = data_points_qs.count()
        print(f"Found {count} data points for the selected range.") # Debugging

        # --- Data Thinning ---
        MAX_GRAPH_POINTS = 500 
        data_points = [] # Initialize as empty list
        if count > MAX_GRAPH_POINTS:
            step = max(1, count // MAX_GRAPH_POINTS) 
            # Apply slicing and THEN convert to list
            data_points = list(data_points_qs[::step]) 
            # --- FIX: Use len() for the list ---
            print(f"Thinned data from {count} to {len(data_points)} points (step={step})") 
        elif count > 0:
             # Convert to list only if there's data
             data_points = list(data_points_qs)
        # If count is 0, data_points remains an empty list

    except Exception as e:
         print(f"Error querying or thinning database: {e}")
         return JsonResponse({'status': 'error', 'message': 'Error retrieving data from database.'}, status=500)
    
    # --- [START OF MODIFICATION] ---
    # Delete the old time formatting logic
    # duration_days = (end_time - start_time).days
    # time_format = '%H:%M' 
    # if duration_days > 7: time_format = '%m-%d' 
    # elif duration_days > 1: time_format = '%m-%d %Hh' 

    # --- Prepare Data ---
    # Handle potential None values when creating datasets
    data = {
        # ALWAYS return the full ISO 8601 timestamp string.
        # The browser (Chart.js + moment.js) will handle the display formatting.
        'labels': [dp.timestamp.isoformat() for dp in data_points],
        'datasets': {
            'weight': [dp.weight_calibrated if dp.weight_calibrated is not None else None for dp in data_points],
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
    # --- [END OF MODIFICATION] ---
    return JsonResponse(data)

def journal_api(request):
    """API to get or save farm journal entries."""
    if request.method == 'GET':
        date_str = request.GET.get('date')
        if not date_str: return HttpResponseBadRequest("Date parameter is required.")
        
        # Construct the expected image path relative to the static root
        image_name = f"{date_str}.jpg"
        image_relative_path = os.path.join('omnitor', 'journal_images', image_name)
        image_url = staticfiles_storage.url(image_relative_path)

        # Check if the actual image file exists
        # Note: This check relies on the MEDIA_ROOT/STATIC_ROOT settings for accuracy in production
        # In development with runserver, Django handles static files differently.
        # A more robust check might involve checking the filesystem directly if needed,
        # but relying on the URL and letting the browser handle 404 is usually sufficient.
        
        try:
            entry = FarmJournal.objects.get(date=date_str)
            return JsonResponse({
                'status': 'found',
                'farm_work': entry.farm_work, 'pesticide': entry.pesticide,
                'fertilizer': entry.fertilizer, 'harvest': entry.harvest,
                'notes': entry.notes, 'image_url': image_url,
Section 2
            })
        except FarmJournal.DoesNotExist:
             # Even if no DB entry, provide the expected image URL
             # The frontend will handle cases where the image doesn't load
            return JsonResponse({'status': 'not_found', 'image_url': image_url})
        except Exception as e:
            print(f"Error fetching journal entry for {date_str}: {e}")
Section 3
            return JsonResponse({'status': 'error', 'message': 'Failed to retrieve journal entry.'}, status=500)
        

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.pop('date', None) # Safely get date
            if not date_str:
section 4
                return HttpResponseBadRequest("Date is required to save journal entry.")

            # Validate date format before proceeding
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
Section 5
            except ValueError:
                 return HttpResponseBadRequest("Invalid date format. Use YYYY-MM-DD.")

Next Section
            # Ensure only expected fields are saved
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

