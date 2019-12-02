import os
import pytest
import yaml

from pocs.core import POCS
from pocs.observatory import Observatory
from pocs.camera import create_cameras_from_config
from pocs.mount import create_mount_from_config
from pocs.scheduler import create_scheduler_from_config
from pocs.utils.location import create_location_from_config

from pocs.utils import error


@pytest.fixture
def observatory(config_with_simulated_mount, images_dir):
    """Return a valid Observatory instance with a specific config."""
    config = config_with_simulated_mount
    site_details = create_location_from_config(config)
    scheduler = create_scheduler_from_config(config, observer=site_details['observer'])
    mount = create_mount_from_config(config)
    obs = Observatory(config=config,
                      scheduler=scheduler,
                      mount=mount,
                      ignore_local_config=True)
    cameras = create_cameras_from_config(config)
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    return obs


def test_bad_state_machine_file():
    with pytest.raises(error.InvalidConfig):
        POCS.load_state_table(state_table_name='foo')


def test_load_bad_state(observatory):
    pocs = POCS(observatory)

    with pytest.raises(error.InvalidConfig):
        pocs._load_state('foo')


def test_load_state_info(observatory):
    pocs = POCS(observatory)

    pocs._load_state('ready', state_info={'tags': ['at_twilight']})
    pocs.next_state = 'ready'
    pocs.goto_next_state()


def test_state_machine_absolute(temp_file):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    with open(temp_file, 'w') as f:
        f.write(yaml.dump(state_table))

    file_path = os.path.abspath(temp_file)
    assert POCS.load_state_table(state_table_name=file_path)
