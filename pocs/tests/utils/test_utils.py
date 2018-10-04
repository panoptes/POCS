import os
import pytest

import time
from datetime import datetime as dt
from astropy import units as u

from pocs.utils import current_time
from pocs.utils import listify
from pocs.utils import load_module
from pocs.utils import CountdownTimer
from pocs.utils import error
from pocs.camera import list_connected_cameras


def test_error():
    with pytest.raises(Exception) as e_info:
        raise error.PanError(msg='Testing message')

    assert str(e_info.value) == 'PanError: Testing message'

    with pytest.raises(Exception) as e_info:
        raise error.PanError()

    assert str(e_info.value) == 'PanError'

    with pytest.raises(SystemExit) as e_info:
        raise error.PanError(msg="Testing exit", exit=True)
    assert e_info.type == SystemExit
    assert str(e_info.value) == 'PanError: Testing exit'


def test_bad_load_module():
    with pytest.raises(error.NotFound):
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

    for arg, expected_duration in [(2, 2.0), (0.5, 0.5), (1 * u.second, 1.0)]:
        timer = CountdownTimer(arg)
        assert timer.duration == expected_duration


def test_countdown_timer():
    count_time = 1
    timer = CountdownTimer(count_time)
    assert timer.time_left() > 0
    assert timer.expired() is False
    assert timer.is_non_blocking is False

    counter = 0.
    while timer.time_left() > 0:
        time.sleep(0.1)
        counter += 0.1

    assert counter == pytest.approx(1)
    assert timer.time_left() == 0
    assert timer.expired() is True
