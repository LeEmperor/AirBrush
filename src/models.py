from enum import Enum

class SensorType(Enum):
    ACCELEROMETER_WAKEUP = "android.sensor.accelerometer"
    MAGNETOMETER_WAKEUP = "android.sensor.magnetic_field"
    GYROSCOPE_WAKEUP = "android.sensor.gyroscope"
    TMD2755_AMBIENT_LIGHT_SENSOR_WAKEUP = "android.sensor.light"
    ICP101XX_PRESSURE_SENSOR_WAKEUP = "android.sensor.pressure"
    TMD2755_PROXIMITY_SENSOR_WAKEUP = "android.sensor.proximity"
    GRAVITY = "android.sensor.gravity"
    LINEAR_ACCELERATION = "android.sensor.linear_acceleration"
    ROTATION_VECTOR = "android.sensor.rotation_vector"
    MMC5603x_MAGNETOMETER_UNCALIBRATED = "android.sensor.magnetic_field_uncalibrated"
    GAME_ROTATION_VECTOR = "android.sensor.game_rotation_vector"
    ICM4X6XX_GYROSCOPE_UNCALIBRATED = "android.sensor.gyroscope_uncalibrated"
    PEDOMETER_WAKEUP = "android.sensor.step_detector"