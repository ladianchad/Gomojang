from django.db import models
import math

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
    
    # Air sensors
    air_temperature = models.FloatField(null=True, blank=True)
    air_humidity = models.FloatField(null=True, blank=True)
    co2 = models.FloatField(null=True, blank=True)
    insolation = models.FloatField(null=True, blank=True)
    
    # Water sensors
    water_temperature = models.FloatField(null=True, blank=True)
    
    # Weight
    weight_raw = models.FloatField(null=True, blank=True)
    weight_calibrated = models.FloatField(null=True, blank=True)
    
    # pH
    ph_voltage = models.FloatField(null=True, blank=True)
    ph_calibrated = models.FloatField(null=True, blank=True)
    
    # EC
    ec_voltage = models.FloatField(null=True, blank=True)
    ec_calibrated = models.FloatField(null=True, blank=True)

    # Soil sensors (from Modbus)
    soil_temperature = models.FloatField(null=True, blank=True)
    soil_humidity = models.FloatField(null=True, blank=True)
    soil_conductivity = models.FloatField(null=True, blank=True)
    soil_ph = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class CalibrationSettings(models.Model):
    id = models.IntegerField(primary_key=True, default=1, editable=False)

    # Weight settings
    weight_offset = models.FloatField(default=0.0)
    weight_scale = models.FloatField(default=1.0)
    
    # pH two-point calibration data
    ph_point1_voltage = models.FloatField(default=2.5)
    ph_point1_value = models.FloatField(default=7.0)
    ph_point2_voltage = models.FloatField(default=3.0)
    ph_point2_value = models.FloatField(default=4.0)
    ph_slope = models.FloatField(default=-5.8)
    ph_intercept = models.FloatField(default=21.5)

    # EC two-point calibration data
    ec_point1_voltage = models.FloatField(default=0.5)
    ec_point1_value = models.FloatField(default=700.0)
    ec_point2_voltage = models.FloatField(default=1.0)
    ec_point2_value = models.FloatField(default=1500.0)
    ec_slope = models.FloatField(default=1.0)
    ec_intercept = models.FloatField(default=0.0)

    def save(self, *args, **kwargs):
        # Calculate pH slope and intercept
        v1_ph, v2_ph = self.ph_point1_voltage, self.ph_point2_voltage
        ph1, ph2 = self.ph_point1_value, self.ph_point2_value
        if (v2_ph - v1_ph) != 0:
            self.ph_slope = (ph2 - ph1) / (v2_ph - v1_ph)
            self.ph_intercept = ph1 - self.ph_slope * v1_ph

        # Calculate EC slope and intercept using the complex formula
        v1_ec, v2_ec = self.ec_point1_voltage, self.ec_point2_voltage
        ec1, ec2 = self.ec_point1_value, self.ec_point2_value

        # Apply the polynomial formula to get "base EC" values (assuming 25占쏙옙C for calibration)
        base_ec1 = (133.42 * math.pow(v1_ec, 3)) - (255.86 * math.pow(v1_ec, 2)) + (857.39 * v1_ec)
        base_ec2 = (133.42 * math.pow(v2_ec, 3)) - (255.86 * math.pow(v2_ec, 2)) + (857.39 * v2_ec)

        if (base_ec2 - base_ec1) != 0:
            self.ec_slope = (ec2 - ec1) / (base_ec2 - base_ec1)
            self.ec_intercept = ec1 - self.ec_slope * base_ec1
            
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

