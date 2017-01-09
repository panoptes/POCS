# Tests for the SBIG camera
import pytest
from ctypes.util import find_library

# Can't test anything unless the SBIG Universal Driver/Library is installed
# If can't find it skip all tests in this module
pytestmark = pytest.mark.skipif(find_library('sbigudrv') is None, reason="Could not find SBIG camera driver")

import os
import time
import sys
sys.path.append('../../')

import astropy.units as u
import astropy.io.fits as fits

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
        assert abs(camera.CCD_set_point - 25 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enable is False
    else:
        # No cameras were found by the driver so the camera should not be connected
        pytest.xfail(reason="No cameras detected")


def test_camera_init_set_point():
    """
    Create a camera instance with a specified CCD cooling set point. This will get the handle to the first available
    camera, retrieve camera info, set the setpoint and enable cooling.
    """
    camera = Camera(set_point=0 * u.Celsius)
    if camera._SBIGDriver._camera_info.camerasFound > 0:
        assert camera._connected is True
        assert camera._handle != INVALID_HANDLE_VALUE
        assert abs(camera.CCD_set_point - 0 * u.Celsius) < 0.5 * u.Celsius
        assert camera.CCD_cooling_enabled is True
    else:
        # No cameras were found by the driver so the camera should not be connected
        pytest.xfail(reason="No cameras detected")


def test_camera_bad_serial():
    """
    Attempt to create a camera instance for a specific non-existent camera.
    """
    camera = Camera(port='NOTAREALSERIALNUMBER')
    assert camera._connected is False
    assert camera._handle == INVALID_HANDLE_VALUE


@pytest.fixture(scope="module")
def camera():
    # Camera init thoroughly tested now, use this camera instance for subsequent tests
    cam = Camera()
    if cam._connected is False:
        # Couldn't connect to a camera, should xfail all tests that try to do something with one
        pytest.xfail(reason="Could not connect to a camera")
    return cam


def test_camera_get_set_set_point(camera):
    """
    Tests the getters & setters for CCD cooling set point
    """
    # Set set point to 10C
    camera.CCD_set_point = 10 * u.Celsius
    assert abs(camera.CCD_set_point - 10 * u.Celsius) < 0.5 * u.Celsius
    assert camera.CCD_cooling_enabled is True
    # Disable cooling
    camera.CCD_set_point = None
    assert abs(camera.CCD_set_point - 25 * u.Celsius) < 0.5 * u.Celsius
    assert camera.CCD_cooling_enabled is False


def test_camera_exposure(camera, tmpdir):
    """
    Tests basic take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure.fits'))
    # A one second normal exposure.
    camera.take_exposure(filename=fits_path)
    # By default take_exposure is non-blocking, need to give it time to complete.
    time.sleep(5)
    # FITS file should now exist. That's a good start.
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Light Frame'


def test_camera_exposure_blocking(camera, tmpdir):
    """
    Tests blocking take_exposure functionality
    """
    fits_path = str(tmpdir.join('test_exposure_blocking.fits'))
    # A one second exposure, command should block until complete
    camera.take_exposure(filename=fits_path, blocking=True)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Light Frame'


def test_camera_exposure_dark(camera, tmpdir):
    """
    Tests taking a dark
    """
    fits_path = str(tmpdir.join('test_exposure_dark.fits'))
    # A 1 second dark exposure
    camera.take_exposure(filename=fits_path, dark=True, blocking=True)
    assert os.path.exists(fits_path)
    # If can retrieve some header data there's a good chance it's a valid FITS file
    header = fits.getheader(fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Dark Frame'
