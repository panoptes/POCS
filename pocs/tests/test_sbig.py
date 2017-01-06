# Tests for the SBIG camera
import pytest
from ctypes.util import find_library

# Can't test anything unless the SBIG Universal Driver/Library is installed
# If can't find it skip all tests in this module
pytestmark = pytest.mark.skipif(find_library('sbigudrv') is None, reason="Could not find SBIG camera driver")

import sys
sys.path.append('../../')

from pocs.camera.sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from pocs.camera.sbig import Camera


def test_driver_init():
    """
    Create an instance of SBIGDriver class. If this completes without raising any exceptions all is good.
    """
    sbig_driver = SBIGDriver()


def test_driver_bad_path():
    """
    Manually specify an incorrect path for the SBIG shared library. The CDLL loader should raise OSError when it fails.
    """
    with pytest.raises(OSError):
        sbig_driver = SBIGDriver(library_path='no_library_here')


def test_camera_init():
    """
    Create a camera instance with no arguments. This will get the handle to the first available camera, retrieve camera
    info and disable cooling, exercising a lot of code along the way.
    """
    camera = Camera()
    if camera._SBIGDriver._camera_info.camerasFound > 0:
        assert camera._connected is True
        assert camera._handle != INVALID_HANDLE_VALUE
    else:
        # No cameras were found by the driver so the camera should not be connected
        pytest.xfail(reason="No cameras detected")


def test_camera_bad_serial():
    """
    Attempt to create a camera instance for a camera with a non-existent serial number.
    """
    camera = Camera(port='NOTAREALSERIALNUMBER')
    assert camera._connected is False
    assert camera._handle == INVALID_HANDLE_VALUE
