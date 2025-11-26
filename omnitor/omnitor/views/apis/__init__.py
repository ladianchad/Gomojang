import calibration
import camera_time
import current_data
import historical_data
import journal
import setting

urlpatterns = [
    calibration.api_path,
    camera_time.api_path,
    current_data.api_path,
    historical_data.api_path,
    journal.api_path,
    setting.api_path
]