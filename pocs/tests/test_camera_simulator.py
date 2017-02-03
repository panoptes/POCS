import pytest

from pocs.camera.simulator import Camera
from pocs.focuser.simulator import Focuser
from pocs.utils.error import NotFound


def test_camera_init():
    sim_camera = Camera()
    assert sim_camera.uid == '999999'
    assert sim_camera.is_connected is False


def test_camera_create_focuser():
    sim_camera = Camera(focuser={'model': 'simulator', 'focus_port': '/dev/ttyFAKE'})
    assert isinstance(sim_camera.focuser, Focuser)


def test_camera_passed_focuser():
    sim_focuser = Focuser(port='/dev/ttyFAKE')
    sim_camera = Camera(focuser=sim_focuser)
    assert sim_camera.focuser is sim_focuser


def test_camera_bad_focuser():
    with pytest.raises((AttributeError, ImportError, NotFound)):
        sim_camera = Camera(focuser={'model': 'NOTAFOCUSER'})


def test_camera_worse_focuser():
    sim_camera = Camera(focuser='NOTAFOCUSER')
    # Will log an error but raise no exceptions
    assert sim_camera.focuser is None


def test_camera_string():
    sim_camera = Camera()
    assert str(sim_camera) == 'Generic Camera (999999) on None'
    sim_camera = Camera(name='Sim', port='/dev/ttyFAKE')
    assert str(sim_camera) == 'Sim (999999) on /dev/ttyFAKE'


def test_camera_connect():
    sim_camera = Camera()
    assert sim_camera.is_connected is False
    sim_camera.connect()
    assert sim_camera.is_connected


def test_camera_file_extension():
    sim_camera = Camera()
    assert sim_camera.file_extension == 'fits'
    sim_camera = Camera(file_extension='FIT')
    assert sim_camera.file_extension == 'FIT'


def test_camera_readout_time():
    sim_camera = Camera()
    assert sim_camera.readout_time == 5.0
    sim_camera = Camera(readout_time=2.0)
    assert sim_camera.readout_time == 2.0
