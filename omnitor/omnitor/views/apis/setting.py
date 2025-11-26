from django.http import JsonResponse, HttpResponseBadRequest, HttpRequest
from django.contrib.staticfiles.storage import staticfiles_storage

from omnitor.models.models import CalibrationSettings
import json


def get_handler(request: HttpRequest): 
    settings = CalibrationSettings.load()
    return JsonResponse(
            {
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
    )

def post_handler(request: HttpRequest):
    try:
        data = json.loads(request.body)
        changed = False
        settings = CalibrationSettings.load()
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
    