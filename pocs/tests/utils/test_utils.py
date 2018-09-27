import os
import pytest

import time
from datetime import datetime as dt

from pocs.utils import current_time
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils import CountdownTimer
from pocs.utils.error import NotFound
from pocs.camera import list_connected_cameras


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


def test_countdown_timer_bad_input():
    with pytest.raises(ValueError):
        assert CountdownTimer('d')

    with pytest.raises(ValueError):
        assert CountdownTimer(current_time())

    with pytest.raises(AssertionError):
        assert CountdownTimer(-1)


def test_countdown_timer_non_blocking():
    timer = CountdownTimer(0)
    assert timer.is_non_blocking
    assert timer.time_left() == 0


def test_countdown_timer():
    timer = CountdownTimer(1)
    assert timer.time_left() > 0
    assert timer.expired() is False
    assert timer.is_non_blocking is False
    time.sleep(1)
    assert timer.time_left() == 0
    assert timer.expired() is True
