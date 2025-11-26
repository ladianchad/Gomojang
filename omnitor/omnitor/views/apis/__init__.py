from .calibration import api_path as calibration_api_path
from .camera_time import api_path as camera_time_api_path
from .current_data import api_path as current_data_api_path
from .historical_data import api_path as historical_data_api_path
from .journal import api_path as journal_api_path
from .setting import api_path as setting_api_path

urlpatterns = [
    calibration_api_path,
    camera_time_api_path,
    current_data_api_path,
    historical_data_api_path,
    journal_api_path,
    setting_api_path
]