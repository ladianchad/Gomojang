from django.urls import path
from . import views

urlpatterns = [
    # 1. Main dashboard page
    path('dashboard/', views.sensor_dashboard_view, name='dashboard'),

    # 2. API for latest data (for Tab 1)
    path('latest_data_api/', views.latest_data_api, name='latest_data_api'),

    # 3. API for historical graph data (for Tab 2)
    path('historical_data_api/', views.historical_data_api, name='historical_data_api'),

    # 4. API for live calibration actions (for Tab 4)
    path('calibration_api/', views.calibration_api, name='calibration_api'),
    
    # 5. API to get and save calibration settings (for Tab 4)
    path('settings_api/', views.settings_api, name='settings_api'),
]
