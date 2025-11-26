from django.apps import AppConfig
import os

class OmnitorConfig(AppConfig):
    name = "omnitor"

    def ready(self):
        # runserver autoreload 2번 실행 방지
        if os.environ.get("RUN_MAIN") != "true":
            return

        from .serial_manager import SerialSingleton

        serial = SerialSingleton.instance()
        serial.start()
