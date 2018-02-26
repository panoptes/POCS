import os
import pytest

from datetime import datetime as dt

from pocs.utils import current_time
from pocs.utils import list_connected_cameras
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils.error import NotFound


def test_bad_load_module():
    with pytest.raises(NotFound):
        load_module('FOOBAR')


def test_listify():
    assert listify(12) == [12]
    assert listify([1, 2, 3]) == [1, 2, 3]


def test_empty_listify():
    assert listify(None) == []


def test_pretty_time():
    t0 = '2016-08-13 10:00:00'
    os.environ['POCSTIME'] = t0

    t1 = current_time(pretty=True)
    assert t1 == t0

    t2 = current_time(flatten=True)
    assert t2 != t0
    assert t2 == '20160813T100000'

    t3 = current_time(datetime=True)
    assert t3 == dt(2016, 8, 13, 10, 0, 0)


def test_list_connected_cameras():
    ports = list_connected_cameras()
    assert isinstance(ports, list)


def test_has_camera_ports():
    ports = list_connected_cameras()
    assert isinstance(ports, list)

    for port in ports:
        assert port.startswith('usb:')
