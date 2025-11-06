from django.urls import path
from . import views

urlpatterns = [
    path('', views.sensor_dashboard_view, name='sensor_dashboard'),
    path('api/latest-data/', views.latest_data_api, name='latest_data_api'),
    path('api/historical-data/', views.historical_data_api, name='historical_data_api'),
    path('api/settings/', views.settings_api, name='settings_api'),
    path('api/calibrate/', views.calibration_api, name='calibration_api'),
    path('api/journal/', views.journal_api, name='journal_api'),
    path('api/camera-time/', views.camera_time_api, name='camera_time_api'),
]
