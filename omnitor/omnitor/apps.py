from django.apps import AppConfig
import os

class OmnitorConfig(AppConfig):
    name = "omnitor"

    def ready(self):
        # runserver autoreload 2번 실행 방지
        if os.environ.get("RUN_MAIN") != "true":
            return

        from .devices.arduino import SerialSingleton

        serial = SerialSingleton.instance()
        serial.start()
        from .services import schedule, arduino, image_logging
        schedule.add_time_interval_shedule("raw_data_write", 1, arduino.update_serial_data)
        image_logging.set_image_logging()