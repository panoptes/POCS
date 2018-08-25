import logging
import os
import subprocess
import signal
import time

import pytest
import Pyro4

from pocs.utils import pyro


def end_process(proc):
    proc.send_signal(signal.SIGINT)
    return_code = proc.wait()


@pytest.fixture(scope='module')
def name_server(request):
    ns_cmds = [os.path.expandvars('$POCS/scripts/pyro_name_server.py'),
               '--host', 'localhost']
    ns_proc = subprocess.Popen(ns_cmds)
    request.addfinalizer(lambda: end_process(ns_proc))
    # Give name server time to start up
    time.sleep(5)
    return ns_proc


@pytest.fixture(scope='module')
def camera_server(name_server, request):
    cs_cmds = [os.path.expandvars('$POCS/scripts/pyro_camera_server.py'),
               '--ignore_local']
    cs_proc = subprocess.Popen(cs_cmds)
    request.addfinalizer(lambda: end_process(cs_proc))
    # Give camera server time to start up
    time.sleep(3)
    return cs_proc


def test_get_own_ip():
    ip = pyro.get_own_ip()
    assert ip


def test_get_own_ip_verbose():
    ip = pyro.get_own_ip(verbose=True)
    assert ip


def test_get_own_ip_logger():
    logger = logging.getLogger()
    ip = pyro.get_own_ip(logger=logger)
    assert ip


def test_name_server(name_server):
    # Check that it's running.
    assert name_server.poll() is None


def test_locate_name_server(name_server):
    # Check that we can connect to the name server
    Pyro4.locateNS(host='localhost')


def test_camera_server(camera_server):
    # Check that it's running.
    assert camera_server.poll() is None


def test_camera_detection(camera_server):
    ns = Pyro4.locateNS(host='localhost')
    cameras = ns.list(metadata_all={'POCS', 'Camera'})
    # Should be one distributed camera, a simulator with simulated focuser
    assert len(cameras) == 1
