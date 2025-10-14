from django.db import models

class SensorData(models.Model):
    # The time when the data was recorded. Defaults to the current time.
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Sensor values. null=True allows for missing values if a sensor fails.
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    co2 = models.FloatField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data recorded at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
