import pytest

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


def test_forwarder(forwarder):
    assert forwarder.is_alive() is True
