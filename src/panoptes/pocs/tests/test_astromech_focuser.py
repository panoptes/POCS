import time

import pytest
from threading import Thread

from panoptes.utils.config.helpers import load_config

from panoptes.pocs.focuser.astromechanics import Focuser as AstroMechFocuser

params = [AstroMechFocuser]
ids = ['astromechanics']


# Ugly hack to access id inside fixture


@pytest.fixture(scope='function', params=zip(params, ids), ids=ids)
def focuser(request):
    # Load the local config file and look for focuser configurations of the specified type
    focuser_configs = []
    local_config = load_config('/Users/Jaime/Documents/MacquarieUni/Projects/POCS/conf_files/pocs.yaml', load_local=True)
    camera_info = local_config.get('cameras')
    if camera_info:
        # Local config file has a cameras section
        camera_configs = camera_info.get('devices')
        if camera_configs:
            # Local config file camera section has a devices list
            for camera_config in camera_configs:
                if camera_config:
                    focuser_config = camera_config.get('focuser', None)
                    if focuser_config and focuser_config['model'] == request.param[1]:
                        # Camera config has a focuser section, and it's the right type
                        focuser_configs.append(focuser_config)

    if not focuser_configs:
        pytest.skip(
            "Found no {} configurations in pocs_local.yaml, skipping tests".format(
                request.param[1]))

    # Create and return a Focuser based on the first config
    return request.param[0](**focuser_configs[0])


@pytest.fixture(scope='function')
def tolerance(focuser):
    """
    Tolerance for confirming focuser has moved to the requested position. The Birger may be
    1 or 2 encoder steps off.
    """
    return 2


def test_init(focuser):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected


def test_move_to(focuser, tolerance):
    focuser.position
    new_pos = 1000
    focuser.move_to(new_pos)
    focuser.position
    pos = int(focuser.position)
    assert pos == pytest.approx(new_pos, abs=tolerance)


def test_move_by(focuser, tolerance):
    focuser.position
    previous_position = int(focuser.position)
    increment = -50
    focuser.move_by(increment)
    focuser.position
    assert int(focuser.position) == pytest.approx(previous_position + increment, abs=tolerance)


def test_is_ready(focuser):
    move_thread = Thread(target=focuser.move_by, args=[13])
    assert not focuser.is_moving
    assert focuser.is_ready
    move_thread.start()
    time.sleep(0.01)
    assert focuser.is_moving
    assert not focuser.is_ready
    move_thread.join()
    assert not focuser.is_moving
    assert focuser.is_ready
