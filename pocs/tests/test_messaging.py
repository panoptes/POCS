import multiprocessing
import pytest
import time

from datetime import datetime
from pocs.utils.messaging import PanMessaging


@pytest.fixture(scope='function')
def forwarder():
    ready = multiprocessing.Event()
    done = multiprocessing.Event()

    def start_forwarder():
        PanMessaging.create_forwarder(
            12345, 54321, ready_fn=lambda: ready.set(), done_fn=lambda: done.set())

    messaging = multiprocessing.Process(target=start_forwarder)
    messaging.start()

    if not ready.wait(timeout=10.0):
        raise Exception('Forwarder failed to become ready!')
    # Wait a moment for the forwarder to start using those sockets.
    time.sleep(0.05)

    yield messaging

    # Stop the forwarder. Since we use the same ports in multiple
    # tests, we wait for the process to shutdown.
    messaging.terminate()
    for _ in range(100):
        # We can't be sure that the sub-process will succeed in
        # calling the done_fn, so we also check for the process
        # ending.
        if done.wait(timeout=0.01):
            break
        if not messaging.is_alive():
            break


@pytest.fixture(scope='function')
def sub():
    messaging = PanMessaging.create_subscriber(54321)

    yield messaging
    messaging.close()


@pytest.fixture(scope='function')
def pub():
    messaging = PanMessaging.create_publisher(12345, bind=False, connect=True)
    yield messaging
    messaging.close()


def test_forwarder(forwarder):
    assert forwarder.is_alive() is True


def test_send_string(forwarder, sub, pub):
    pub.send_message('TEST-CHANNEL', 'Hello')
    msg_type, msg_obj = sub.receive_message()

    assert msg_type == 'TEST-CHANNEL'
    assert isinstance(msg_obj, dict)
    assert 'message' in msg_obj
    assert msg_obj['message'] == 'Hello'


def test_send_datetime(forwarder, sub, pub):
    pub.send_message('TEST-CHANNEL', {'date': datetime(2017, 1, 1)})
    msg_type, msg_obj = sub.receive_message()
    assert msg_obj['date'] == '2017-01-01T00:00:00'


def test_send_mongo_objectid(forwarder, sub, pub, config, db):
    db.insert_current('config', {'foo': 'bar'})
    pub.send_message('TEST-CHANNEL', db.get_current('config'))
    msg_type, msg_obj = sub.receive_message()
    assert '_id' in msg_obj
    assert isinstance(msg_obj['_id'], str)

    db.current.remove({'type': 'config'})
