import pytest

from pocs.focuser.simulator import Focuser as SimFocuser
from pocs.focuser.birger import Focuser as BirgerFocuser
from pocs.camera.simulator import Camera
from pocs.utils.config import load_config

from serial import SerialException


@pytest.fixture(scope='module', params=[SimFocuser, BirgerFocuser], ids=['simulator', 'birger'])
def focuser(request):
    if request.param == SimFocuser:
        return request.param()
    elif request.param == BirgerFocuser:
        # Load the local config file and look for Birger focuser configurations
        birger_configs = []
        local_config = load_config('pocs_local', ignore_local=True)
        camera_info = local_config.get('cameras')
        if camera_info:
            # Local config file has a cameras section
            camera_configs = camera_info.get('devices')
            if camera_configs:
                # Local config file camera section has a devices list
                for camera_config in camera_configs:
                    focuser_config = camera_config.get('focuser', None)
                    if focuser_config and focuser_config['model'] == 'birger':
                        # Camera config has a focuser section, and it's for a Birger
                        birger_configs.append(focuser_config)

        if not birger_configs:
            pytest.skip("Found no Birger focuser configurations in pocs_local.yaml, skipping tests")

        # Create and return a Birger Focuser based on the first config
        return request.param(**birger_configs[0])
    else:
        pytest.fail("Don't know what to do with this Focuser subclass!")


@pytest.fixture(scope='module')
def tolerance(focuser):
    """
    Tolerance for confirming focuser has moved to the requested position. The Birger may be
    1 or 2 encoder steps off.
    """
    if isinstance(focuser, SimFocuser):
        return 0
    elif isinstance(focuser, BirgerFocuser):
        return 2


def test_focuser_init(focuser):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected
    # Expect UID to be a string (or integer?) of non-zero length? Just assert its True
    assert focuser.uid


def test_focuser_move_to(focuser, tolerance):
    focuser.move_to(100)
    assert abs(focuser.position - 100) <= tolerance


def test_focuser_move_by(focuser, tolerance):
    previous_position = focuser.position
    increment = -13
    focuser.move_by(increment)
    assert abs(focuser.position - (previous_position + increment)) <= tolerance


def test_position_setter(focuser, tolerance):
    """
    Can assign to position property as an alternative to move_to() method
    """
    focuser.position = 75
    assert abs(focuser.position - 75) <= tolerance


def test_camera_association(focuser):
    """
    Test association of Focuser with Camera after initialisation (getter, setter)
    """
    sim_camera_1 = Camera()
    sim_camera_2 = Camera()
    # Cameras in the fixture haven't been associated with a Camera yet, this should work
    focuser.camera = sim_camera_1
    assert focuser.camera is sim_camera_1
    # Attempting to associate with a second Camera should fail, though.
    focuser.camera = sim_camera_2
    assert focuser.camera is sim_camera_1


def test_camera_init():
    """
    Test focuser init via Camera constructor/
    """
    sim_camera = Camera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, SimFocuser)
    assert sim_camera.focuser.is_connected
    assert sim_camera.focuser.uid == 'SF9999'
    assert sim_camera.focuser.camera is sim_camera


def test_camera_association_on_init():
    """
    Test association of Focuser with Camera during Focuser init
    """
    sim_camera = Camera()
    focuser = SimFocuser(camera=sim_camera)
    assert focuser.camera is sim_camera
