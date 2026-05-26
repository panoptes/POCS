"""Tests for POCSConfig and related config models."""

from astropy import units as u

from panoptes.pocs.config import (
    CameraDefaultsConfig,
    CamerasConfig,
    MountConfig,
    MountSerialConfig,
    NetworkConfig,
    ObservationsConfig,
    POCSConfig,
    PointingConfig,
    SchedulerConfig,
    SchedulerConstraintConfig,
)

# ---------------------------------------------------------------------------
# POCSConfig — round-trip from a dict
# ---------------------------------------------------------------------------


def test_pocsconfig_from_dict():
    """POCSConfig validates cleanly from a typical pocs.yaml dict."""
    data = {
        "name": "Test Unit",
        "pan_id": "PAN001",
        "location": {
            "name": "Test Site",
            "latitude": "19.54 deg",
            "longitude": "-155.58 deg",
            "elevation": "3400.0 m",
            "horizon": "30 deg",
            "timezone": "US/Hawaii",
        },
        "mount": {
            "brand": "ioptron",
            "model": "cem40",
            "driver": "panoptes.pocs.mount.ioptron.cem40",
            "serial": {"port": "/dev/ttyUSB0", "baudrate": 115200},
        },
        "scheduler": {
            "type": "panoptes.pocs.scheduler.dispatch",
            "fields_file": "tess_sectors_north.yaml",
            "constraints": [
                {"name": "panoptes.pocs.scheduler.constraint.Altitude"},
                {
                    "name": "panoptes.pocs.scheduler.constraint.MoonAvoidance",
                    "options": {"separation": 15},
                },
            ],
        },
        "cameras": {
            "defaults": {"exptime": 60.0, "file_extension": "cr2"},
            "devices": [{"model": "panoptes.pocs.camera.gphoto.canon.Camera", "name": "Cam00"}],
        },
    }

    cfg = POCSConfig.model_validate(data)

    assert cfg.name == "Test Unit"
    assert cfg.pan_id == "PAN001"
    assert cfg.location.latitude == 19.54 * u.deg
    assert cfg.mount.brand == "ioptron"
    assert cfg.mount.serial.baudrate == 115200
    assert len(cfg.scheduler.constraints) == 2
    assert cfg.scheduler.constraints[1].options["separation"] == 15
    assert cfg.cameras.defaults.exptime == 60.0
    assert len(cfg.cameras.devices) == 1


def test_pocsconfig_defaults():
    """POCSConfig provides sensible defaults for all sections."""
    cfg = POCSConfig()

    assert cfg.wait_delay == 180
    assert cfg.max_transition_attempts == 5
    assert cfg.state_machine == "panoptes"
    assert isinstance(cfg.mount, MountConfig)
    assert isinstance(cfg.scheduler, SchedulerConfig)
    assert isinstance(cfg.cameras, CamerasConfig)
    assert isinstance(cfg.observations, ObservationsConfig)
    assert isinstance(cfg.panoptes_network, NetworkConfig)


def test_pocsconfig_extra_keys_allowed():
    """Unknown top-level keys do not cause validation errors."""
    cfg = POCSConfig.model_validate({"name": "X", "custom_key": "custom_value"})
    assert cfg.name == "X"


# ---------------------------------------------------------------------------
# MountConfig
# ---------------------------------------------------------------------------


def test_mount_config_defaults():
    cfg = MountConfig()
    assert cfg.serial.port == "/dev/ttyUSB0"
    assert cfg.serial.baudrate == 9600


def test_mount_serial_config():
    cfg = MountSerialConfig(port="/dev/ttyACM0", baudrate=115200)
    assert cfg.port == "/dev/ttyACM0"
    assert cfg.baudrate == 115200


# ---------------------------------------------------------------------------
# SchedulerConfig
# ---------------------------------------------------------------------------


def test_scheduler_constraint_options():
    c = SchedulerConstraintConfig(
        name="panoptes.pocs.scheduler.constraint.MoonAvoidance", options={"separation": 20}
    )
    assert c.options["separation"] == 20


def test_scheduler_config_empty_constraints():
    cfg = SchedulerConfig()
    assert cfg.constraints == []


# ---------------------------------------------------------------------------
# CamerasConfig
# ---------------------------------------------------------------------------


def test_cameras_config_defaults():
    cfg = CamerasConfig()
    assert cfg.defaults.exptime == 120.0
    assert cfg.devices == []


def test_camera_defaults_extra_keys():
    cfg = CameraDefaultsConfig.model_validate({"exptime": 30, "cooling": {"enabled": True}})
    assert cfg.exptime == 30


# ---------------------------------------------------------------------------
# PointingConfig
# ---------------------------------------------------------------------------


def test_pointing_config_max_attempts_zero():
    cfg = PointingConfig()
    assert cfg.max_attempts == 0  # disabled by default


# ---------------------------------------------------------------------------
# load_config integration
# ---------------------------------------------------------------------------


def test_load_config_with_pocs_model(tmp_path):
    """load_config(model=POCSConfig) returns a validated POCSConfig instance."""
    from panoptes.utils.config.helpers import load_config
    from panoptes.utils.serializers import to_yaml

    cfg_file = tmp_path / "pocs_test.yaml"
    cfg_file.write_text(
        to_yaml(
            {
                "name": "Integration Unit",
                "pan_id": "PAN042",
                "location": {
                    "latitude": "10 deg",
                    "longitude": "20 deg",
                    "elevation": "100 m",
                },
                "mount": {"brand": "ioptron", "driver": "panoptes.pocs.mount.simulator"},
            }
        )
    )

    cfg = load_config(cfg_file, model=POCSConfig, load_local=False)

    assert isinstance(cfg, POCSConfig)
    assert cfg.name == "Integration Unit"
    assert cfg.pan_id == "PAN042"
    assert cfg.mount.brand == "ioptron"
    # Defaults are present even though not in file.
    assert cfg.wait_delay == 180
