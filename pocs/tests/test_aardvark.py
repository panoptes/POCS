# Named after an African nocturnal insectivore because for mysterious reasons these
# tests were failing if run towards the end of the test suite.
import logging
import os

import pytest
import Pyro4

from pocs.utils.pyro import get_own_ip


def test_get_own_ip():
    ip = get_own_ip()
    assert ip


def test_get_own_ip_verbose():
    ip = get_own_ip(verbose=True)
    assert ip


def test_get_own_ip_logger():
    logger = logging.getLogger()
    ip = get_own_ip(logger=logger)
    assert ip


def test_name_server(name_server):
    # Check that it's running.
    assert name_server.poll() is None


def test_locate_name_server(name_server):
    # Check that we can connect to the name server
    Pyro4.locateNS()


def test_camera_server(camera_server):
    # Check that it's running.
    assert camera_server.poll() is None


def test_camera_detection(camera_server):
    with Pyro4.locateNS() as ns:
        cameras = ns.list(metadata_all={'POCS', 'Camera'})
    # Should be one distributed camera, a simulator with simulated focuser
    assert len(cameras) == 1
