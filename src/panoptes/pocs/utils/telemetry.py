from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from panoptes.utils.time import current_time


class TelemetryBase(BaseModel):
    """Base model for all telemetry."""
    model_config = ConfigDict(extra="allow")

    timestamp: datetime = Field(default_factory=lambda: current_time().datetime)
    type: str


class WeatherReading(TelemetryBase):
    """Weather station reading."""
    type: str = "weather"
    ambient_temp: float
    sky_temp: float
    wind_speed: float
    rain_frequency: int
    pwm: float
    cloud_condition: str
    wind_condition: str
    rain_condition: str
    cloud_safe: bool
    wind_safe: bool
    rain_safe: bool
    is_safe: bool


class PowerReading(TelemetryBase):
    """Power board reading."""
    type: str = "power"
    ac_ok: bool | None = None
    battery_low: bool | None = None
    mount: float | None = None
    fans: float | None = None
    weather_station: float | None = None
    # Add other relays as needed based on specific hardware configuration


class SafetyStatus(TelemetryBase):
    """Combined safety status."""
    type: str = "safety"
    ac_power: bool
    is_dark: bool
    good_weather: bool
    free_space_root: bool
    free_space_images: bool


class StateMachineState(TelemetryBase):
    """State machine transition."""
    type: str = "state"
    source: str
    dest: str


class ImageMetadata(TelemetryBase):
    """Metadata for a captured image."""
    type: str = "images"
    camera_name: str
    camera_uid: str
    field_name: str
    field_ra: float
    field_dec: float
    exptime: float
    filepath: str
    filter: str
    image_id: str
    sequence_id: str
    start_time: str
    airmass: float | None = None
    priority: float | None = None


class ObservatoryStatus(TelemetryBase):
    """General observatory status."""
    type: str = "status"
    state: str
    next_state: str | None = None
    mount_ra: float | None = None
    mount_dec: float | None = None
    mount_state: str | None = None
    is_parked: bool
    sun_alt: float
    moon_alt: float
    moon_illumination: float
