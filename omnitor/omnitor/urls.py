from django.urls import path
from .views import (
    sensor_dashboard_view, 
    latest_data_api, 
    historical_data_api, 
    settings_api, 
    calibration_api,
    journal_api 
)

urlpatterns = [
    # Dashboard and Sensor APIs
    path('dashboard/', sensor_dashboard_view, name='dashboard'),
    path('latest_data_api/', latest_data_api, name='latest_data_api'),
    path('historical_data_api/', historical_data_api, name='historical_data_api'),

    # Calibration APIs
    path('settings_api/', settings_api, name='settings_api'),
    path('calibration_api/', calibration_api, name='calibration_api'),
    
    # Journal API
    path('journal_api/', journal_api, name='journal_api'),
]
