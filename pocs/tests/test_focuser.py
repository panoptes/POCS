import pytest

from pocs.focuser.simulator import Focuser as SimFocuser
from pocs.focuser.birger import Focuser as BirgerFocuser
from pocs.camera.simulator import Camera

from serial import SerialException


@pytest.fixture(scope='module', params=[SimFocuser, BirgerFocuser], ids=['simulator', 'birger'])
def focuser(request):
    if request.param == SimFocuser:
        return request.param()
    elif request.param == BirgerFocuser:
        # No automatic way to find ports for Birger Focusers, need to specify manually
        try:
            focuser = request.param(port='/dev/tty.USA49WG2P4.4')
            return focuser
        except SerialException:
            # Error opening the serial port, probably because the specified port doesn't exist.
            # Can't tell if this is expected, have to assume that it is.
            pytest.xfail("Couldn't open serial port, assuming there's no Birger Focuser to test")
        except AssertionError:
            # Error in communucating with the Birger adaptor. Probably means there isn't one on
            # this port, or it hasn't got power. Can't tell if this is expected, assume it is.
            pytest.xfail("Couldn't commuicate with Birger Focuser, assuming there isn't one to test")
    else:
        pytest.fail("Don't know what to do with this Focuser subclass!")


@pytest.fixture(scope='module')
def uid(focuser):
    """
    Expected serial numbers. No way of predicting this for Birger Focusers, this will need
    to be changed manually.
    """
    if isinstance(focuser, SimFocuser):
        return 'SF9999'
    elif isinstance(focuser, BirgerFocuser):
        return '10858'
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


def test_focuser_init(focuser, uid):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected
    assert focuser.uid == uid


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


def test_camera_init():
    """
    Test focuser init via Camera constructor.
    """
    sim_camera = Camera(focuser='simulator', focus_port='/dev/ttyFAKE')
    assert isinstance(sim_camera.focuser, SimFocuser)
    assert sim_camera.focuser.is_connected
    assert sim_camera.focuser.uid == 'SF9999'
