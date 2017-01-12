import pytest

from pocs.focuser.simulator import Focuser


@pytest.fixture(scope='module')
def focuser():
    return Focuser()


def test_focuser_init(focuser):
    """
    Confirm proper init & exercise some of the property getters
    """
    assert focuser.is_connected
    assert focuser.uid == 'SF9999'
    assert focuser.position == 0


def test_focuser_move_to(focuser):
    focuser.move_to(100)
    assert focuser.position == 100


def test_focuser_move_by(focuser):
    previous_position = focuser.position
    increment = -13
    focuser.move_by(increment)
    assert focuser.position == previous_position + increment


def test_position_setter(focuser):
    """
    Can assign to position property as an alternative to move_to() method
    """
    focuser.position = -75
    assert focuser.position == -75
