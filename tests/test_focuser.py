import time
from contextlib import suppress

import pytest
from threading import Thread

from panoptes.utils.config.helpers import load_config
from panoptes.utils import error

from panoptes.pocs.focuser.simulator import Focuser as SimFocuser
from panoptes.pocs.focuser.birger import Focuser as BirgerFocuser
from panoptes.pocs.focuser.astromechanics import Focuser as AstroMechanicsFocuser
from panoptes.pocs.focuser.focuslynx import Focuser as FocusLynxFocuser
from panoptes.pocs.camera.simulator.dslr import Camera

params = [SimFocuser, BirgerFocuser, FocusLynxFocuser, AstroMechanicsFocuser]
ids = ['simulator', 'birger', 'focuslynx', 'astromechanics']


@pytest.fixture(scope='function', params=zip(params, ids), ids=ids)
def focuser(request):
    FocusClass = request.param[0]
    model_name = request.param[1]
    if FocusClass == SimFocuser:
        # Simulated focuser, just create one and return it
        return FocusClass()
    else:
        # Load the local config file and look for focuser configurations of the specified type
        focuser_configs = []
        local_config = load_config('pocs_local', load_local=True)
        with suppress(KeyError):
            device_info = local_config['cameras']['devices']
            for camera_config in device_info:
                focuser_config = camera_config['focuser']
                if 'model' in focuser_config and focuser_config['model'] == model_name:
                    focuser_configs.append(focuser_config)

        if not focuser_configs:
            pytest.skip(f"Found no {model_name} config, skipping tests")

        # Create and return a Focuser based on the first matching config.
        return FocusClass(**focuser_configs[0])


@pytest.fixture(scope='function')
def tolerance(focuser):
    """
    Tolerance for confirming focuser has moved to the requested position. The Birger may be
    1 or 2 encoder steps off.
    """
    if isinstance(focuser, SimFocuser):
        return 0
    elif isinstance(focuser, BirgerFocuser):
        return 2
    elif isinstance(focuser, AstroMechanicsFocuser):
        return 2
    elif isinstance(focuser, FocusLynxFocuser):
        return 0


def test_init(focuser):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected
    # Expect UID to be a string (or integer?) of non-zero length? Just assert its True
    assert focuser.uid


def test_move_to(focuser, tolerance):
    new_position = focuser.move_to(100)
    assert focuser.position == new_position
    assert focuser.position == pytest.approx(100, abs=tolerance)


def test_move_by(focuser, tolerance):
    previous_position = focuser.move_to(100)
    increment = -13
    new_position = focuser.move_by(increment)
    assert new_position == pytest.approx((previous_position + increment), abs=tolerance)


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


def test_position_setter(focuser, tolerance):
    """
    Can assign to position property as an alternative to move_to() method
    """
    focuser.position = 75
    assert focuser.position == pytest.approx(75, abs=tolerance)


def test_move_below_min_position(focuser, tolerance):
    if isinstance(focuser, AstroMechanicsFocuser):
        pytest.skip("This does not exist for astromechanics, skipping test")
    focuser.move_to(focuser.min_position - 100)
    assert focuser.position == pytest.approx(focuser.min_position, tolerance)


def test_move_above_max_position(focuser, tolerance):
    if isinstance(focuser, AstroMechanicsFocuser):
        pytest.skip("This does not exist for astromechanics, skipping test")
    focuser.move_to(focuser.max_position + 100)
    assert focuser.position == pytest.approx(focuser.max_position, tolerance)


def test_camera_association(focuser):
    """ Test association of Focuser with Camera after initialisation (getter, setter) """
    sim_camera_1 = Camera()
    sim_camera_2 = Camera()
    # Cameras in the fixture haven't been associated with a Camera yet, this should work
    focuser.camera = sim_camera_1
    assert focuser.camera is sim_camera_1
    # Attempting to associate with a second Camera should fail, though.
    focuser.camera = sim_camera_2
    assert focuser.camera is sim_camera_1


def test_camera_init():
    """ Test focuser init via Camera constructor """
    sim_camera = Camera(focuser={'model': 'panoptes.pocs.focuser.simulator.Focuser',
                                 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, SimFocuser)
    assert sim_camera.focuser.is_connected
    assert sim_camera.focuser.uid
    assert sim_camera.focuser.camera is sim_camera


def test_camera_association_on_init():
    """ Test association of Focuser with Camera during Focuser init """
    sim_camera = Camera()
    focuser = SimFocuser(camera=sim_camera)
    assert focuser.camera is sim_camera


def test_astromechs_find_fail(focuser, tolerance, caplog):
    v_id = 0xf00
    p_id = 0xba2
    with pytest.raises(error.NotFound):
        AstroMechanicsFocuser(vendor_id=v_id, product_id=p_id)
