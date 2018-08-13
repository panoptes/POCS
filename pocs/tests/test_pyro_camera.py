import subprocess
import time
import os

from astropy.io import fits
import glob
import Pyro4
import pytest

from pocs.camera.pyro import Camera


@pytest.fixture(scope='module')
def name_server():
    ns_cmd = '$POCS/scripts/pyro_name_server.py --host 127.0.0.1'
    with subprocess.Popen(ns_cmd, shell=True) as ns_proc:
        yield ns_proc
        ns_proc.terminate()


@pytest.fixture(scope='module')
def camera_server(name_server):
    cs_cmd = '$POCS/scripts/pyro_camera_server.py --ignore_local'
    with subprocess.Popen(cs_cmd, shell=True) as cs_proc:
        yield cs_proc
        cs_proc.terminate()


@pytest.fixture(scope='module')
def camera(camera_server):
    return Camera()


def test_name_server(name_server):
    # Give name server time to start up
    time.sleep(5)
    # Check that it's running.
    assert name_server.poll() is None


def test_locate_name_server(name_server):
    # Check that we can connect to the name server
    Pyro4.locateNS(host='127.0.0.1')


def test_camera_server(camera_server):
    # Give camera server time to start up
    time.sleep(1)
    # Check that it's running.
    assert camera_server.poll() is None


def test_camera_connect(camera):
    # Check that camera has connected to the server and got the uid
    uid = camera.uids['camera.simulator.001']
    assert len(uid) == 6
    assert uid[0:2] == 'SC'


def test_take_exposure(camera, tmpdir):
    fits_path = str(tmpdir.join('<uid>/test_exposure.fits'))
    event = camera.take_exposure(seconds=1, filename=fits_path)
    event.wait()
    real_fits_path = glob.glob(str(tmpdir.join('*/test_exposure.fits')))[0]
    assert os.path.exists(real_fits_path)
    header = fits.getheader(real_fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Light Frame'


def test_take_exposure_blocking(camera, tmpdir):
    fits_path = str(tmpdir.join('test_exposure_blocking.fits'))
    camera.take_exposure(filename=fits_path, dark=True, blocking=True)
    real_fits_path = glob.glob(str(tmpdir.join('*/test_exposure_blocking.fits')))[0]
    assert os.path.exists(real_fits_path)
    header = fits.getheader(real_fits_path)
    assert header['EXPTIME'] == 1.0
    assert header['IMAGETYP'] == 'Dark Frame'
