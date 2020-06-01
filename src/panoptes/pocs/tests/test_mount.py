import pytest
from contextlib import suppress

from panoptes.pocs import hardware
from panoptes.pocs.mount import AbstractMount
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.utils.location import create_location_from_config

from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config


def test_create_mount_simulator():
    # Use the simulator create function directly.
    mount = create_mount_simulator()
    assert isinstance(mount, AbstractMount) is True


def test_create_mount_simulator_with_config(dynamic_config_server, config_port):
    # Remove mount from list of simulators.
    set_config('simulator', hardware.get_all_names(without=['mount']))
    # But setting the driver to `simulator` should return simulator.
    set_config('mount.driver', 'simulator', port=config_port)

    mount = create_mount_from_config(config_port=config_port)
    assert isinstance(mount, AbstractMount) is True


def test_create_mount_without_mount_info(dynamic_config_server, config_port):
    # Set the mount config to none and then don't pass anything for error.
    set_config('mount', None, port=config_port)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(config_port=config_port, mount_info=None)


def test_create_mount_with_mount_info(dynamic_config_server, config_port):
    # Pass the mount info directly with nothing in config.
    mount_info = get_config('mount', port=config_port)
    mount_info['driver'] = 'simulator'

    # Remove info from config.
    set_config('mount', None, port=config_port)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    assert isinstance(create_mount_from_config(config_port=config_port,
                                               mount_info=mount_info), AbstractMount) is True


def test_create_mount_with_earth_location(dynamic_config_server, config_port):
    # Get location to pass manually.
    loc = create_location_from_config()
    # Set config to not have a location.
    set_config('location', None, port=config_port)
    assert isinstance(create_mount_from_config(config_port=config_port,
                                               earth_location=loc), AbstractMount) is True


def test_create_mount_without_earth_location(dynamic_config_server, config_port):
    set_config('location', None, port=config_port)
    with pytest.raises(error.PanError):
        create_mount_from_config(config_port=config_port, earth_location=None)


def test_bad_mount_port(dynamic_config_server, config_port):
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator', port=config_port)
    with suppress(KeyError):
        simulators.remove('mount')
    set_config('simulator', simulators, port=config_port)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.port', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(config_port=config_port)


def test_bad_mount_driver(dynamic_config_server, config_port):
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator', port=config_port)
    with suppress(KeyError):
        simulators.remove('mount')
    set_config('simulator', simulators, port=config_port)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.driver', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(config_port=config_port)
