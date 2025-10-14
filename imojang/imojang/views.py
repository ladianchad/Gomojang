from django.shortcuts import render
from django.http import JsonResponse
from .models import SensorData
import json

def sensor_dashboard_view(request):
    # Renders the main HTML page for the dashboard.
    return render(request, 'imojang/serial_display.html')

def latest_data_api(request):
    #API endpoint to return the latest sensor data as JSON.
    #This version includes all sensor data.
    try:
        latest_data = SensorData.objects.latest('timestamp')
        data = {
            'timestamp': latest_data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'temperature': latest_data.temperature,
            'humidity': latest_data.humidity,
            'co2': latest_data.co2,
            'weight': latest_data.weight,
        }
        return JsonResponse(data)
    except SensorData.DoesNotExist:
        return JsonResponse({
            'timestamp': 'N/A', 'temperature': 'N/A', 'humidity': 'N/A',
            'co2': 'N/A', 'weight': 'N/A',
        })

def historical_data_api(request):
    #API endpoint to return recent data points for the graph.
    #Now includes all sensor data.
    all_data = SensorData.objects.order_by('timestamp')
    count = all_data.count()
    data_points = all_data[max(0, count - 60):count]

    data = {
        'labels': [d.timestamp.strftime('%H:%M') for d in data_points],
        'temperature': [d.temperature for d in data_points],
        'humidity': [d.humidity for d in data_points],
        'co2': [d.co2 for d in data_points],
        'weight': [d.weight for d in data_points],
    }
    return JsonResponse(data)

