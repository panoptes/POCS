import subprocess
import time
import os
import glob
import signal

from astropy.io import fits
import Pyro4
import pytest

from pocs.camera.pyro import Camera


@pytest.fixture(scope='module')
def name_server(request):
    print('Starting name server')
    ns_cmds = [os.path.expandvars('$POCS/scripts/pyro_name_server.py'), '--host', '127.0.0.1']
    ns_proc = subprocess.Popen(ns_cmds)
    yield ns_proc
    print('Sending SIGINT to name server ({})'.format(ns_proc.pid))
    ns_proc.send_signal(signal.SIGINT)
    return_code = ns_proc.wait()
    print('Name server ({}) terminated, return code {}'.format(ns_proc.pid, return_code))


@pytest.fixture(scope='module')
def camera_server(name_server, request):
    print('Starting camera server')
    cs_cmds = [os.path.expandvars('$POCS/scripts/pyro_camera_server.py'), '--ignore_local']
    cs_proc = subprocess.Popen(cs_cmds)
    yield cs_proc
    print('Sending SIGINT to camera server ({})'.format(cs_proc.pid))
    cs_proc.send_signal(signal.SIGINT)
    return_code = cs_proc.wait()
    print('Camera server ({}) terminated, return code {}'.format(cs_proc.pid, return_code))


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
    time.sleep(2)
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


def test_autofocus_fine(camera):
    event = camera.autofocus()
    event.wait()


def test_autofocus_coarse(camera):
    event = camera.autofocus(coarse=True)
    event.wait()
