import pytest

from pocs.focuser.simulator import Focuser as SimFocuser
from pocs.camera.simulator import Camera


# Ugly hack to access id inside fixture
@pytest.fixture(scope='function')
def focuser():
    # Simulated focuser, just create one and return it
    return SimFocuser()


@pytest.fixture(scope='function')
def tolerance(focuser):
    """
    Tolerance for confirming focuser has moved to the requested position. The Birger may be
    1 or 2 encoder steps off.
    """
    return 0


def test_init(focuser):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected
    # Expect UID to be a string (or integer?) of non-zero length? Just assert its True
    assert focuser.uid


def test_move_to(focuser, tolerance):
    focuser.move_to(100)
    assert focuser.position == pytest.approx(100, abs=tolerance)


def test_move_by(focuser, tolerance):
    focuser.move_to(100)
    previous_position = focuser.position
    increment = -13
    focuser.move_by(increment)
    assert focuser.position == pytest.approx((previous_position + increment), abs=tolerance)


def test_position_setter(focuser, tolerance):
    """
    Can assign to position property as an alternative to move_to() method
    """
    focuser.position = 75
    assert focuser.position == pytest.approx(75, abs=tolerance)


def test_move_below_min_position(focuser, tolerance):
    focuser.move_to(focuser.min_position - 100)
    assert focuser.position == pytest.approx(focuser.min_position, tolerance)


def test_move_above_max_positons(focuser, tolerance):
    focuser.move_to(focuser.max_position + 100)
    assert focuser.position == pytest.approx(focuser.max_position, tolerance)


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
    sim_camera = Camera(focuser={'model': 'simulator',
                                 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, SimFocuser)
    assert sim_camera.focuser.is_connected
    assert sim_camera.focuser.uid
    assert sim_camera.focuser.camera is sim_camera


def test_camera_association_on_init():
    """
    Test association of Focuser with Camera during Focuser init
    """
    sim_camera = Camera()
    focuser = SimFocuser(camera=sim_camera)
    assert focuser.camera is sim_camera
