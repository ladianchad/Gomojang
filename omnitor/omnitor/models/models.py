from django.db import models

class FarmJournal(models.Model):
    date = models.DateField(primary_key=True)
    farm_work = models.TextField(blank=True, null=True)
    pesticide = models.TextField(blank=True, null=True)
    fertilizer = models.TextField(blank=True, null=True)
    harvest = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Journal for {self.date}"

class SensorData(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # 환경
    air_temperature = models.FloatField(null=True, blank=True)
    air_humidity = models.FloatField(null=True, blank=True)
    co2 = models.FloatField(null=True, blank=True)
    insolation = models.FloatField(null=True, blank=True)

    # 무게
    weight_raw = models.FloatField(null=True, blank=True)
    weight_calibrated = models.FloatField(null=True, blank=True)
    
    # 수온
    water_temperature = models.FloatField(null=True, blank=True)
    
    # pH
    ph_voltage = models.FloatField(null=True, blank=True)
    ph_calibrated = models.FloatField(null=True, blank=True)
    
    # EC
    ec_voltage = models.FloatField(null=True, blank=True)
    ec_calibrated = models.FloatField(null=True, blank=True)

    # 티핑게이지
    tip_count = models.FloatField(null=True, blank=True)
    tip_total = models.FloatField(null=True, blank=True)
    
    # 토양 센서서
    soil_temperature = models.FloatField(null=True, blank=True)
    soil_humidity = models.FloatField(null=True, blank=True)
    soil_conductivity = models.FloatField(null=True, blank=True)
    soil_ph = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class CalibrationSettings(models.Model):
    # 무게 보정
    weight_point1_raw = models.FloatField(default=20000)
    weight_point1_value = models.FloatField(default=0)
    weight_point2_raw = models.FloatField(default=40000)
    weight_point2_value = models.FloatField(default=2000)
    weight_slope = models.FloatField(default=-21.5)
    weight_intercept = models.FloatField(default=20000)
    
    # pH 보정
    ph_point1_voltage = models.FloatField(default=2.5)
    ph_point1_value = models.FloatField(default=7.0)
    ph_point2_voltage = models.FloatField(default=3.0)
    ph_point2_value = models.FloatField(default=4.0)
    ph_slope = models.FloatField(default=-5.8)
    ph_intercept = models.FloatField(default=21.5)

    # EC 보정
    ec_point1_voltage = models.FloatField(default=0.5)
    ec_point1_value = models.FloatField(default=700.0)
    ec_point2_voltage = models.FloatField(default=1.0)
    ec_point2_value = models.FloatField(default=1500.0)
    ec_slope = models.FloatField(default=1.0)
    ec_intercept = models.FloatField(default=0.0)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

