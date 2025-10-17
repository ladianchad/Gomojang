from django.db import models
from django.utils import timezone

class SensorData(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    air_temperature = models.FloatField(null=True, blank=True)
    air_humidity = models.FloatField(null=True, blank=True)
    co2 = models.FloatField(null=True, blank=True)
    lux = models.FloatField(null=True, blank=True)
    weight_raw = models.FloatField(null=True, blank=True)
    weight_calibrated = models.FloatField(null=True, blank=True)
    ph_voltage = models.FloatField(null=True, blank=True)
    ph_calibrated = models.FloatField(null=True, blank=True)
    ec_raw = models.FloatField(null=True, blank=True)
    ec_calibrated = models.FloatField(null=True, blank=True)
    soil_temperature = models.FloatField(null=True, blank=True)
    soil_humidity = models.FloatField(null=True, blank=True)
    soil_conductivity = models.FloatField(null=True, blank=True)
    soil_ph = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

class CalibrationSettings(models.Model):
    weight_offset = models.FloatField(default=0.0)
    weight_scale = models.FloatField(default=1.0)
    ph_point1_value = models.FloatField(default=7.0)
    ph_point1_voltage = models.FloatField(default=2.5)
    ph_point2_value = models.FloatField(default=4.0)
    ph_point2_voltage = models.FloatField(default=3.0)
    ph_slope = models.FloatField(default=-5.55)
    ph_intercept = models.FloatField(default=21.38)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        v1, p1 = self.ph_point1_voltage, self.ph_point1_value
        v2, p2 = self.ph_point2_voltage, self.ph_point2_value
        if (v1 is not None and v2 is not None and v1 != v2):
            self.ph_slope = (p2 - p1) / (v2 - v1)
            self.ph_intercept = p1 - self.ph_slope * v1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Global Calibration Settings"

class FarmJournal(models.Model):
    date = models.DateField(primary_key=True, default=timezone.now)
    
    farm_work = models.TextField(blank=True, null=True, verbose_name="?띿옉??)
    pesticide = models.TextField(blank=True, null=True, verbose_name="?띿빟")
    fertilizer = models.TextField(blank=True, null=True, verbose_name="鍮꾨즺")
    harvest = models.TextField(blank=True, null=True, verbose_name="?섑솗")
    notes = models.TextField(blank=True, null=True, verbose_name="?뱀씠?ы빆")

    def __str__(self):
        return f"?띿옣?쇱? - {self.date.strftime('%Y-%m-%d')}"

