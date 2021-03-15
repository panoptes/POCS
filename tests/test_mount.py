from contextlib import suppress

import pytest
from panoptes.pocs import hardware
from panoptes.pocs.mount import AbstractMount
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.utils.location import create_location_from_config
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.config.client import set_config
from panoptes.utils.serializers import to_json
import requests


def reset_conf(config_host, config_port):
    url = f'http://{config_host}:{config_port}/reset-config'
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


def test_create_mount_simulator(config_host, config_port):
    # Use the simulator create function directly.
    mount = create_mount_simulator()
    assert isinstance(mount, AbstractMount) is True


def test_create_mount_simulator_with_config(config_host, config_port):
    # Remove mount from list of simulators.
    set_config('simulator', hardware.get_all_names(without=['mount']))
    # But setting the driver to `simulator` should return simulator.
    set_config('mount.driver', 'panoptes.pocs.mount.simulator')

    mount = create_mount_from_config()
    assert isinstance(mount, AbstractMount) is True
    reset_conf(config_host, config_port)


def test_create_mount_without_mount_info(config_host, config_port):
    # Set the mount config to none and then don't pass anything for error.
    set_config('mount', None)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(mount_info=None)

    reset_conf(config_host, config_port)


def test_create_mount_with_mount_info(config_host, config_port):
    # Pass the mount info directly with nothing in config.
    mount_info = get_config('mount', default=dict())
    mount_info['driver'] = 'panoptes.pocs.mount.simulator'

    # Remove info from config.
    set_config('mount', None)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    assert isinstance(create_mount_from_config(mount_info=mount_info), AbstractMount) is True

    reset_conf(config_host, config_port)


def test_create_mount_with_earth_location(config_host, config_port):
    # Get location to pass manually.
    loc = create_location_from_config()
    # Set config to not have a location.
    set_config('location', None)
    set_config('simulator', hardware.get_all_names())
    assert isinstance(create_mount_from_config(earth_location=loc['earth_location']),
                      AbstractMount) is True

    reset_conf(config_host, config_port)


def test_create_mount_without_earth_location(config_host, config_port):
    set_config('location', None)
    with pytest.raises(error.PanError):
        create_mount_from_config(earth_location=None)
    reset_conf(config_host, config_port)


def test_bad_mount_port(config_host, config_port):
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator')
    with suppress(KeyError, AttributeError):
        simulators.pop('mount')
    set_config('simulator', simulators)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.port', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf(config_host, config_port)


def test_bad_mount_driver(config_host, config_port):
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator')
    with suppress(KeyError, AttributeError):
        simulators.pop('mount')
    set_config('simulator', simulators)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.driver', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf(config_host, config_port)
