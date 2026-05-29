"""Data models for the POCS terminal dashboard skeleton."""

from collections import deque
from dataclasses import dataclass, field

SPARKLINE_LEN = 40


@dataclass(slots=True)
class SafetyModel:
    """Safety and environmental status for operator awareness."""

    ac_power: bool = False
    is_dark: bool = False
    good_weather: bool = False
    free_space_root: float = 0.0
    free_space_images: float = 0.0
    age_s: float = 0.0


@dataclass(slots=True)
class MountModel:
    """Mount status values displayed in dashboard and hardware views."""

    connected: bool = False
    is_parked: bool = True
    is_tracking: bool = False
    is_slewing: bool = False
    ra: str = "--"
    dec: str = "--"
    ha: str = "--"
    alt: str = "--"
    az: str = "--"


@dataclass(slots=True)
class CameraModel:
    """Camera status and short exposure progress history."""

    name: str = ""
    connected: bool = False
    is_exposing: bool = False
    temperature: str = "--"
    filter_name: str = "--"
    last_image: str = ""
    progress_hist: deque[float] = field(default_factory=lambda: deque(maxlen=SPARKLINE_LEN))


@dataclass(slots=True)
class ObservationModel:
    """Current observation metadata from the scheduler."""

    field_name: str = ""
    exposure_s: float = 0.0
    current_exp_num: int = 0
    merit: float = 0.0


@dataclass(slots=True)
class SchedulerModel:
    """Scheduler status and active observation details."""

    available_fields: int = 0
    selected_field: str = ""
    observing: ObservationModel = field(default_factory=ObservationModel)


@dataclass(slots=True)
class FocuserModel:
    """Focuser status and position information."""

    connected: bool = False
    position: int = 0
    is_moving: bool = False


@dataclass(slots=True)
class DomeModel:
    """Dome connectivity and motion/open state."""

    connected: bool = False
    is_open: bool = False
    is_moving: bool = False


@dataclass(slots=True)
class SystemModel:
    """Top-level system state derived from running POCS."""

    state: str = "unknown"
    next_state: str = ""
    initialized: bool = False
    connected: bool = False
    free_space: float = 0.0
    uptime: str = "--"


@dataclass(slots=True)
class POCSModel:
    """Complete snapshot consumed by the TUI renderer."""

    safety: SafetyModel = field(default_factory=SafetyModel)
    mount: MountModel = field(default_factory=MountModel)
    cameras: list[CameraModel] = field(default_factory=list)
    scheduler: SchedulerModel = field(default_factory=SchedulerModel)
    focuser: FocuserModel = field(default_factory=FocuserModel)
    dome: DomeModel = field(default_factory=DomeModel)
    system: SystemModel = field(default_factory=SystemModel)
    scan_time_ms: float = 0.0
    scan_count: int = 0


__all__ = [
    "SPARKLINE_LEN",
    "CameraModel",
    "DomeModel",
    "FocuserModel",
    "MountModel",
    "ObservationModel",
    "POCSModel",
    "SafetyModel",
    "SchedulerModel",
    "SystemModel",
]
