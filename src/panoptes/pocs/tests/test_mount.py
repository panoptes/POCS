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
from panoptes.utils.serializers import to_json

import requests

config_host = 'localhost'
config_port = 6563
url = f'http://{config_host}:{config_port}/reset-config'


def reset_conf():
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


def test_create_mount_simulator():
    # Use the simulator create function directly.
    mount = create_mount_simulator()
    assert isinstance(mount, AbstractMount) is True


def test_create_mount_simulator_with_config():
    # Remove mount from list of simulators.
    set_config('simulator', hardware.get_all_names(without=['mount']))
    # But setting the driver to `simulator` should return simulator.
    set_config('mount.driver', 'simulator')

    mount = create_mount_from_config()
    assert isinstance(mount, AbstractMount) is True
    reset_conf()


def test_create_mount_without_mount_info():
    # Set the mount config to none and then don't pass anything for error.
    set_config('mount', None)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    with pytest.raises(error.MountNotFound):
        create_mount_from_config(mount_info=None)

    reset_conf()


def test_create_mount_with_mount_info():
    # Pass the mount info directly with nothing in config.
    mount_info = get_config('mount', default=dict())
    mount_info['driver'] = 'simulator'

    # Remove info from config.
    set_config('mount', None)
    set_config('simulator', hardware.get_all_names(without=['mount']))
    assert isinstance(create_mount_from_config(mount_info=mount_info), AbstractMount) is True

    reset_conf()


def test_create_mount_with_earth_location():
    # Get location to pass manually.
    loc = create_location_from_config()
    # Set config to not have a location.
    set_config('location', None)
    assert isinstance(create_mount_from_config(earth_location=loc['earth_location']), AbstractMount) is True

    reset_conf()


def test_create_mount_without_earth_location():
    set_config('location', None)
    with pytest.raises(error.PanError):
        create_mount_from_config(earth_location=None)
    reset_conf()


def test_bad_mount_port():
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator')
    with suppress(KeyError, ValueError):
        simulators.remove('mount')
    set_config('simulator', simulators)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.port', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf()


def test_bad_mount_driver():
    # Remove the mount from the list of simulators so it thinks we have a real one.
    simulators = get_config('simulator')
    with suppress(KeyError, ValueError):
        simulators.remove('mount')
    set_config('simulator', simulators)

    # Set a bad port, which should cause a fail before actual mount creation.
    set_config('mount.serial.driver', 'foobar')
    with pytest.raises(error.MountNotFound):
        create_mount_from_config()
    reset_conf()
