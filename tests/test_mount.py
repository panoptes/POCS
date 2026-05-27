from contextlib import suppress

import pytest
from astropy.utils.iers import Conf as iers_conf

from panoptes.utils import error

from panoptes.pocs import hardware
from panoptes.utils.config.store import get_config, reload_config, set_config
from panoptes.pocs.mount import AbstractMount, create_mount_from_config, create_mount_simulator
from panoptes.pocs.utils.location import create_location_from_config

iers_conf.iers_degraded_accuracy.set_temp("warn")


def reset_conf():
    reload_config()


def test_create_mount_simulator():
    # Use the simulator create function directly.
    mount = create_mount_simulator()
    assert isinstance(mount, AbstractMount) is True


def test_create_mount_simulator_with_config():
    # Remove mount from list of simulators.
    set_config("simulator", hardware.get_all_names(without=["mount"]))
    # But setting the driver to `simulator` should return simulator.
    set_config("mount.driver", "panoptes.pocs.mount.simulator")

    mount = create_mount_from_config()
    assert isinstance(mount, AbstractMount) is True
    reset_conf()


def test_create_mount_without_mount_info():
    # Set the mount config to none and then don't pass anything for error.
    set_config("mount", None)
    set_config("simulator", hardware.get_all_names(without=["mount"]))
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(mount_info=None)

    reset_conf()


def test_create_mount_with_mount_info():
    # Pass the mount info directly with nothing in config.
    mount_info = get_config("mount", default=dict())
    mount_info["driver"] = "panoptes.pocs.mount.simulator"

    # Remove info from config.
    set_config("mount", None)
    set_config("simulator", hardware.get_all_names(without=["mount"]))
    assert isinstance(create_mount_from_config(mount_info=mount_info), AbstractMount) is True

    reset_conf()


def test_create_mount_with_earth_location():
    # Get location to pass manually.
    loc = create_location_from_config()
    # Set config to not have a location.
    set_config("location", None)
    set_config("simulator", hardware.get_all_names())
    assert isinstance(create_mount_from_config(earth_location=loc.earth_location), AbstractMount) is True

    reset_conf()


def test_create_mount_without_earth_location():
    set_config("location", None)
    with pytest.raises(error.PanError):
        create_mount_from_config(earth_location=None)
    reset_conf()


def test_bad_mount_port():
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config("simulator")
    with suppress(KeyError, AttributeError):
        simulators.pop("mount")
    set_config("simulator", simulators)
    # Use real mount driver.
    set_config("mount.driver", "panoptes.pocs.mount.ioptron.cem40")

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config("mount.serial.port", "foobar")
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf()


def test_bad_mount_driver():
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config("simulator")
    with suppress(KeyError, AttributeError):
        simulators.pop("mount")
    set_config("simulator", simulators)

    # Set a bad driver, which should cause a fail before actual mount creation.
    set_config("mount.driver", "not.a.real.mount")
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf()
