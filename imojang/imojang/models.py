from django.db import models
import json

class CalibrationSettings(models.Model):
    """
    A Singleton model to store system-wide calibration settings.
    This ensures all sensor readings use one consistent set of calibration data.
    """
    # Weight Calibration
    weight_offset = models.FloatField(default=0.0, help_text="The raw reading of the scale with no weight.")
    weight_scale = models.FloatField(default=1.0, help_text="The factor to convert raw units to grams.")

    # pH Two-Point Calibration Data
    ph_point1_voltage = models.FloatField(default=2.5, help_text="Recorded voltage for the first pH calibration point (e.g., at pH 7.0).")
    ph_point1_value = models.FloatField(default=7.0, help_text="The known pH value of the first calibration solution.")
    ph_point2_voltage = models.FloatField(default=1.5, help_text="Recorded voltage for the second pH calibration point (e.g., at pH 4.0).")
    ph_point2_value = models.FloatField(default=4.0, help_text="The known pH value of the second calibration solution.")

    # Calculated pH values
    ph_slope = models.FloatField(default=-5.8, help_text="Calculated slope for the pH voltage-to-pH conversion.")
    ph_intercept = models.FloatField(default=21.5, help_text="Calculated intercept for the pH conversion.")

    def save(self, *args, **kwargs):
        # Ensure only one instance of settings can exist
        self.pk = 1
        # Recalculate slope and intercept whenever the model is saved
        self.calculate_ph_parameters()
        super(CalibrationSettings, self).save(*args, **kwargs)

    def calculate_ph_parameters(self):
        """Calculates the slope and intercept for the pH calibration curve."""
        try:
            # Formula for slope: (y2 - y1) / (x2 - x1)
            # y is pH value, x is voltage
            voltage_diff = self.ph_point2_voltage - self.ph_point1_voltage
            if voltage_diff == 0: # Avoid division by zero
                # Revert to defaults if voltages are the same to prevent errors
                self.ph_slope = -5.8
                self.ph_intercept = 21.5
                return

            ph_diff = self.ph_point2_value - self.ph_point1_value
            self.ph_slope = ph_diff / voltage_diff

            # Formula for intercept: y - mx
            # Using point 1: intercept = y1 - slope * x1
            self.ph_intercept = self.ph_point1_value - self.ph_slope * self.ph_point1_voltage
        except Exception:
            # In case of any other error, revert to defaults
            self.ph_slope = -5.8
            self.ph_intercept = 21.5

    @classmethod
    def load(cls):
        # This is a class method to get the single instance of the settings
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "System Calibration Settings"


class SensorData(models.Model):
    """
    Stores a single reading from all connected sensors.
    Includes both raw and calibrated values.
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Air sensors (from Arduino)
    air_temperature = models.FloatField(null=True, blank=True)
    air_humidity = models.FloatField(null=True, blank=True)
    co2 = models.FloatField(null=True, blank=True)
    lux = models.FloatField(null=True, blank=True)
    
    # Weight values
    weight_raw = models.FloatField(null=True, blank=True)
    weight_calibrated = models.FloatField(null=True, blank=True)
    
    # pH values
    ph_voltage = models.FloatField(null=True, blank=True)
    ph_calibrated = models.FloatField(null=True, blank=True)

    # EC values
    ec_raw = models.FloatField(null=True, blank=True)
    ec_calibrated = models.FloatField(null=True, blank=True)

    # Soil sensors (from Modbus)
    soil_temperature = models.FloatField(null=True, blank=True)
    soil_humidity = models.FloatField(null=True, blank=True)
    soil_conductivity = models.FloatField(null=True, blank=True)
    soil_ph = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Data at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
