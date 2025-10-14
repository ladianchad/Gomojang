"""
URL configuration for imojang project.
"""
from django.urls import path
# Import the new view functions we created
from .views import sensor_dashboard_view, latest_data_api, historical_data_api

urlpatterns = [
    # 1. The URL for the main dashboard page that users will see.
    # e.g., http://your-raspberry-pi-ip/dashboard/
    path('dashboard/', sensor_dashboard_view, name='dashboard'),

    # 2. The API endpoint for the JavaScript to get the latest sensor values.
    # This URL must match the 'fetch' URL in your sensor_display.html file.
    path('latest_data_api/', latest_data_api, name='latest_data_api'),

    # 3. The API endpoint for the JavaScript to get historical data for the graph.
    # This also needs to match the 'fetch' URL in your HTML.
    path('historical_data_api/', historical_data_api, name='historical_data_api'),
]
