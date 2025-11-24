from django.urls import path
from .views import (
    sensor_dashboard_view, 
    latest_data_api, 
    historical_data_api, 
    settings_api, 
    calibration_api,
    journal_api,
    camera_time_api
)

urlpatterns = [
    # 대시보드 (센서 데이터 관련) API
    path('', sensor_dashboard_view, name='dashboard'),
    path('latest_data_api/', latest_data_api, name='latest_data_api'),
    path('historical_data_api/', historical_data_api, name='historical_data_api'),

    # 보정 API
    path('settings_api/', settings_api, name='settings_api'),
    path('calibration_api/', calibration_api, name='calibration_api'),
    
    # 농장 일지 API
    path('journal_api/', journal_api, name='journal_api'),
    
    # 카메라 API
    path('camera_time_api/', camera_time_api, name='camera_time_api'),

]
