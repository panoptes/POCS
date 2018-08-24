import pytest
import logging

from pocs.utils import pyro


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
