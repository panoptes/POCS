"""Typed configuration models for POCS.

Extends the base ``UnitConfig`` from ``panoptes-utils`` with POCS-specific
hardware and runtime sections.  All models use ``extra="allow"`` so that
unknown keys in YAML do not raise validation errors — this keeps the schema
non-breaking as the config file evolves.

Usage::

    from panoptes.utils.config.helpers import load_config
    from panoptes.pocs.config import POCSConfig

    cfg = load_config(model=POCSConfig)
    print(cfg.location.latitude)   # astropy Quantity
    print(cfg.mount.driver)        # str
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from panoptes.utils.config.models import UnitConfig


class MountSerialConfig(BaseModel):
    """Serial port settings for the mount."""

    model_config = ConfigDict(extra="allow")

    port: str = "/dev/ttyUSB0"
    timeout: float = 0.0
    baudrate: int = 9600


class MountConfig(BaseModel):
    """Mount hardware configuration."""

    model_config = ConfigDict(extra="allow")

    brand: str = ""
    model: str = ""
    driver: str = ""
    commands_file: str | None = None
    serial: MountSerialConfig = Field(default_factory=MountSerialConfig)


class PointingConfig(BaseModel):
    """Pointing model correction settings."""

    model_config = ConfigDict(extra="allow")

    max_attempts: int = 0
    auto_correct: bool = True
    threshold: float = 100.0
    exptime: float = 30.0


class SchedulerConstraintConfig(BaseModel):
    """A single scheduler constraint entry."""

    model_config = ConfigDict(extra="allow")

    name: str
    options: dict = Field(default_factory=dict)


class SchedulerConfig(BaseModel):
    """Observation scheduler settings."""

    model_config = ConfigDict(extra="allow")

    type: str = "panoptes.pocs.scheduler.dispatch"
    fields_file: str = "tess_sectors_north.yaml"
    check_file: bool = True
    iers_url: str | None = None
    iers_auto: bool = True
    constraints: list[SchedulerConstraintConfig] = Field(default_factory=list)


class CameraDefaultsConfig(BaseModel):
    """Default settings applied to all cameras unless overridden per device."""

    model_config = ConfigDict(extra="allow")

    primary: str | None = None
    auto_detect: bool = True
    compress_fits: bool = True
    make_pretty_images: bool = True
    keep_jpgs: bool = True
    readout_time: float = 5.0
    timeout: float = 60.0
    exptime: float = 120.0
    filter_type: str = "RGGB"
    file_extension: str = "cr2"


class CamerasConfig(BaseModel):
    """Cameras section: shared defaults plus per-device overrides."""

    model_config = ConfigDict(extra="allow")

    defaults: CameraDefaultsConfig = Field(default_factory=CameraDefaultsConfig)
    devices: list[dict] = Field(default_factory=list)


class ObservationsConfig(BaseModel):
    """Post-observation processing and storage options."""

    model_config = ConfigDict(extra="allow")

    make_timelapse: bool = False
    compress_fits: bool = True
    make_pretty_images: bool = True
    keep_jpgs: bool = False
    plate_solve: bool = False
    upload_image: bool = False


class NetworkBucketsConfig(BaseModel):
    """Google Cloud Storage bucket names."""

    model_config = ConfigDict(extra="allow")

    upload: str = "panoptes-images-incoming"
    images: str | None = None


class NetworkConfig(BaseModel):
    """PANOPTES network and cloud connectivity settings."""

    model_config = ConfigDict(extra="allow")

    use_firestore: bool = False
    cloud_logging_level: str | None = None
    service_account_key: str | None = None
    project_id: str = "panoptes-project-01"
    buckets: NetworkBucketsConfig = Field(default_factory=NetworkBucketsConfig)


class EnvironmentConfig(BaseModel):
    """Environmental sensor configuration (power board, weather station)."""

    model_config = ConfigDict(extra="allow")

    auto_detect: bool = False


class POCSConfig(UnitConfig):
    """Full typed configuration model for a POCS unit.

    Extends :class:`panoptes.utils.config.models.UnitConfig` (which covers
    ``name``, ``pan_id``, ``location``, ``directories``, and ``db``) with
    POCS-specific hardware and runtime sections.

    All sections have sensible defaults so that a partial config file is
    still valid.

    Examples::

        from panoptes.utils.config.helpers import load_config
        from panoptes.pocs.config import POCSConfig

        cfg = load_config(model=POCSConfig)
        assert cfg.mount.brand == "ioptron"
        assert cfg.scheduler.check_file is True
    """

    # Runtime / state-machine tunables.
    wait_delay: int = 180
    max_transition_attempts: int = 5
    max_observing_attempts: int = 3
    status_check_interval: int = 60
    state_machine: str = "panoptes"

    # Hardware sections.
    mount: MountConfig = Field(default_factory=MountConfig)
    pointing: PointingConfig = Field(default_factory=PointingConfig)
    cameras: CamerasConfig = Field(default_factory=CamerasConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)

    # Observation pipeline.
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    observations: ObservationsConfig = Field(default_factory=ObservationsConfig)

    # Cloud / network.
    panoptes_network: NetworkConfig = Field(default_factory=NetworkConfig)
