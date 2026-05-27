"""Tests for POCSConfig and related config models."""

from astropy import units as u

from panoptes.utils.config.store import _get_nested, get_config, init_config, reload_config, set_config

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


# ---------------------------------------------------------------------------
# config/store.py — branch coverage
# ---------------------------------------------------------------------------


def test_get_nested_empty_key():
    """Empty key returns the full dict."""
    d = {"a": 1}
    assert _get_nested(d, "") == d


def test_get_nested_non_dict_traversal():
    """Traversing through a non-dict value returns default."""
    d = {"a": "not-a-dict"}
    assert _get_nested(d, "a.b", default="x") == "x"


def test_get_nested_list_index():
    """List index syntax [N] retrieves the nth element."""
    d = {"items": [10, 20, 30]}
    assert _get_nested(d, "items[1]") == 20


def test_get_nested_list_index_non_list():
    """List index on a non-list value returns default."""
    d = {"items": "not-a-list"}
    assert _get_nested(d, "items[0]", default="x") == "x"


def test_get_nested_list_index_out_of_range():
    """Out-of-range list index returns default."""
    d = {"items": [1, 2]}
    assert _get_nested(d, "items[99]", default="miss") == "miss"


def test_set_config_creates_intermediate_keys():
    """set_config creates missing intermediate dicts."""
    init_config("tests/testing.yaml")
    set_config("brand_new.nested.key", "hello", persist=False)
    assert get_config("brand_new.nested.key") == "hello"
    # cleanup
    reload_config()


def test_set_config_existing_intermediate_dict():
    """set_config traverses existing intermediate dicts without overwriting them."""
    init_config("tests/testing.yaml")
    # 'location' already exists as a dict; set a sub-key without clobbering siblings
    set_config("location.custom_key", "custom_value", persist=False)
    assert get_config("location.custom_key") == "custom_value"
    assert get_config("location.timezone") is not None  # sibling preserved
    # cleanup
    reload_config()


def test_get_config_auto_inits(tmp_path, monkeypatch):
    """get_config auto-initialises from env var when store is empty."""
    import panoptes.utils.config.store as store_mod

    # Force store empty then point env var at testing.yaml
    original = store_mod._CONFIG.copy()
    store_mod._CONFIG.clear()
    monkeypatch.setenv("PANOPTES_CONFIG_FILE", "tests/testing.yaml")
    try:
        val = get_config("name")
        assert val is not None
    finally:
        store_mod._CONFIG.clear()
        store_mod._CONFIG.update(original)


def test_set_config_auto_inits(monkeypatch):
    """set_config auto-initialises when store is empty."""
    import panoptes.utils.config.store as store_mod

    original = store_mod._CONFIG.copy()
    store_mod._CONFIG.clear()
    monkeypatch.setenv("PANOPTES_CONFIG_FILE", "tests/testing.yaml")
    try:
        set_config("name", "override", persist=False)
        assert get_config("name") == "override"
    finally:
        store_mod._CONFIG.clear()
        store_mod._CONFIG.update(original)
