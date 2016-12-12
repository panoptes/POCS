import pytest
import time

from multiprocessing import Process

from pocs.utils.messaging import PanMessaging


@pytest.fixture(scope='function')
def forwarder():
    def start_forwarder():
        PanMessaging('forwarder', (12345, 54321))

    messaging = Process(target=start_forwarder)

    messaging.start()
    yield messaging
    messaging.terminate()


@pytest.fixture(scope='function')
def sub():
    messaging = PanMessaging('subscriber', 54321)

    yield messaging


@pytest.fixture(scope='function')
def pub():
    messaging = PanMessaging('publisher', 12345)
    time.sleep(2)  # Wait for publisher to start up
    yield messaging


def test_forwarder(forwarder):
    assert forwarder.is_alive() is True


def test_messaging(forwarder, sub, pub):
    pub.send_message('TEST-CHANNEL', 'Hello')
    msg_type, msg_obj = sub.receive_message()

    assert msg_type == 'TEST-CHANNEL'
    assert isinstance(msg_obj, dict)
    assert 'message' in msg_obj
    assert msg_obj['message'] == 'Hello'
