import os
import pytest
import signal
import time
from datetime import datetime as dt
from astropy import units as u

from panoptes.utils import current_time
from panoptes.utils import DelaySigTerm
from panoptes.utils import listify
from panoptes.utils import load_module
from panoptes.utils import CountdownTimer
from panoptes.utils import error
from pocs.camera import list_connected_cameras


def test_error(capsys):
    with pytest.raises(error.PanError) as e_info:
        raise error.PanError(msg='Testing message')

    assert str(e_info.value) == 'PanError: Testing message'

    with pytest.raises(error.PanError) as e_info:
        raise error.PanError()

    assert str(e_info.value) == 'PanError'

    with pytest.raises(SystemExit) as e_info:
        raise error.PanError(msg="Testing exit", exit=True)
    assert e_info.type == SystemExit
    assert capsys.readouterr().out.strip() == 'TERMINATING: Testing exit'

    with pytest.raises(SystemExit) as e_info:
        raise error.PanError(exit=True)
    assert e_info.type == SystemExit
    assert capsys.readouterr().out.strip() == 'TERMINATING: No reason specified'


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

    # This will increment one second - see docs
    t2 = current_time(flatten=True)
    assert t2 != t0
    assert t2 == '20160813T100001'

    # This will increment one second - see docs
    t3 = current_time(datetime=True)
    assert t3 == dt(2016, 8, 13, 10, 0, 2)


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


def test_delay_of_sigterm_with_nosignal():
    orig_sigterm_handler = signal.getsignal(signal.SIGTERM)

    with DelaySigTerm():
        assert signal.getsignal(signal.SIGTERM) != orig_sigterm_handler

    assert signal.getsignal(signal.SIGTERM) == orig_sigterm_handler


def test_delay_of_sigterm_with_handled_signal():
    """Confirm that another type of signal can be handled.

    In this test we'll send SIGCHLD, which should immediately call the
    signal_handler the test installs, demonstrating that only SIGTERM
    is affected by this DelaySigTerm.
    """
    test_signal = signal.SIGCHLD

    # Booleans to keep track of how far we've gotten.
    before_signal = False
    after_signal = False
    signal_handled = False
    after_with = False

    def signal_handler(signum, frame):
        assert before_signal

        nonlocal signal_handled
        assert not signal_handled
        signal_handled = True

        assert not after_signal

    old_test_signal_handler = signal.getsignal(test_signal)
    orig_sigterm_handler = signal.getsignal(signal.SIGTERM)
    try:
        # Install our handler.
        signal.signal(test_signal, signal_handler)

        with DelaySigTerm():
            assert signal.getsignal(signal.SIGTERM) != orig_sigterm_handler
            before_signal = True
            # Send the test signal. It should immediately
            # call our handler.
            os.kill(os.getpid(), test_signal)
            assert signal_handled
            after_signal = True

        after_with = True
        assert signal.getsignal(signal.SIGTERM) == orig_sigterm_handler
    finally:
        assert before_signal
        assert signal_handled
        assert after_signal
        assert after_with
        assert signal.getsignal(signal.SIGTERM) == orig_sigterm_handler
        signal.signal(test_signal, old_test_signal_handler)


def test_delay_of_sigterm_with_raised_exception():
    """Confirm that raising an exception inside the handler is OK."""
    test_signal = signal.SIGCHLD

    # Booleans to keep track of how far we've gotten.
    before_signal = False
    after_signal = False
    signal_handled = False
    exception_caught = False

    def signal_handler(signum, frame):
        assert before_signal

        nonlocal signal_handled
        assert not signal_handled
        signal_handled = True

        assert not after_signal
        raise UserWarning()

    old_test_signal_handler = signal.getsignal(test_signal)
    orig_sigterm_handler = signal.getsignal(signal.SIGTERM)
    try:
        # Install our handler.
        signal.signal(test_signal, signal_handler)

        with DelaySigTerm():
            assert signal.getsignal(signal.SIGTERM) != orig_sigterm_handler
            before_signal = True
            # Send the test signal. It should immediately
            # call our handler.
            os.kill(os.getpid(), test_signal)
            # Should not reach this point because signal_handler() should
            # be called because we called:
            #     signal.signal(other-handler, signal_handler)
            after_signal = True
            assert False, "Should not get here!"
    except UserWarning:
        assert before_signal
        assert signal_handled
        assert not after_signal
        assert not exception_caught
        assert signal.getsignal(signal.SIGTERM) == orig_sigterm_handler
        exception_caught = True
    finally:
        # Restore old handler before asserts.
        signal.signal(test_signal, old_test_signal_handler)

        assert before_signal
        assert signal_handled
        assert not after_signal
        assert exception_caught
        assert signal.getsignal(signal.SIGTERM) == orig_sigterm_handler


def test_delay_of_sigterm_with_sigterm():
    """Confirm that SIGTERM is in fact delayed."""

    # Booleans to keep track of how far we've gotten.
    before_signal = False
    after_signal = False
    signal_handled = False

    def signal_handler(signum, frame):
        assert before_signal
        assert after_signal

        nonlocal signal_handled
        assert not signal_handled
        signal_handled = True

    orig_sigterm_handler = signal.getsignal(signal.SIGTERM)
    try:
        # Install our handler.
        signal.signal(signal.SIGTERM, signal_handler)

        with DelaySigTerm():
            before_signal = True
            # Send SIGTERM. It should not call the handler yet.
            os.kill(os.getpid(), signal.SIGTERM)
            assert not signal_handled
            after_signal = True

        assert signal.getsignal(signal.SIGTERM) == signal_handler
        assert before_signal
        assert after_signal
        assert signal_handled
    finally:
        signal.signal(signal.SIGTERM, orig_sigterm_handler)
