import multiprocessing
import pytest
import time

from datetime import datetime
from pocs.utils.messaging import PanMessaging


@pytest.fixture(scope='module')
def mp_manager():
    return multiprocessing.Manager()


@pytest.fixture(scope='function')
def forwarder(mp_manager):
    ready = mp_manager.Event()
    done = mp_manager.Event()

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


def test_forwarder(forwarder):
    assert forwarder.is_alive() is True


@pytest.fixture(scope='function')
def pub_and_sub(forwarder):
    # Ensure that the subscriber is created first.
    sub = PanMessaging.create_subscriber(54321)
    time.sleep(0.05)
    pub = PanMessaging.create_publisher(12345, bind=False, connect=True)
    time.sleep(0.05)
    yield (pub, sub)
    pub.close()
    sub.close()


def test_send_string(pub_and_sub):
    pub, sub = pub_and_sub
    pub.send_message('Test-Topic', 'Hello')
    topic, msg_obj = sub.receive_message()

    assert topic == 'Test-Topic'
    assert isinstance(msg_obj, dict)
    assert 'message' in msg_obj
    assert msg_obj['message'] == 'Hello'


def test_send_datetime(pub_and_sub):
    pub, sub = pub_and_sub
    pub.send_message('Test-Topic', {'date': datetime(2017, 1, 1)})
    topic, msg_obj = sub.receive_message()
    assert msg_obj['date'] == '2017-01-01T00:00:00'


def test_storage_id(pub_and_sub, config, db):
    id0 = db.insert_current('config', {'foo': 'bar'}, store_permanently=False)
    pub, sub = pub_and_sub
    pub.send_message('Test-Topic', db.get_current('config'))
    topic, msg_obj = sub.receive_message()
    assert '_id' in msg_obj
    assert isinstance(msg_obj['_id'], str)
    assert id0 == msg_obj['_id']
