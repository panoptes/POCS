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


################################################################################
# Tests of the conftest.py messaging fixtures.


def test_message_forwarder_exists(message_forwarder):
    assert isinstance(message_forwarder, dict)
    assert 'msg_ports' in message_forwarder

    assert isinstance(message_forwarder['msg_ports'], tuple)
    assert len(message_forwarder['msg_ports']) == 2
    assert isinstance(message_forwarder['msg_ports'][0], int)
    assert isinstance(message_forwarder['msg_ports'][1], int)

    assert isinstance(message_forwarder['cmd_ports'], tuple)
    assert len(message_forwarder['cmd_ports']) == 2
    assert isinstance(message_forwarder['cmd_ports'][0], int)
    assert isinstance(message_forwarder['cmd_ports'][1], int)

    # The ports should be unique.
    msg_ports = message_forwarder['msg_ports']
    cmd_ports = message_forwarder['cmd_ports']

    ports = set(list(msg_ports) + list(cmd_ports))
    assert len(ports) == 4


def assess_pub_sub(pub, sub):
    """Helper method for testing a pub-sub pair."""

    # Can not send a message using a subscriber
    with pytest.raises(Exception):
        sub.send_message('topic_name', 'a string')

    # Can not receive a message using a publisher
    assert (None, None) == pub.receive_message(blocking=True)

    # At first, there is nothing available to receive.
    assert (None, None) == sub.receive_message(blocking=True, timeout_ms=500)

    pub.send_message('topic.name', 'a string')
    topic, msg_obj = sub.receive_message()
    assert isinstance(msg_obj, dict)
    assert 'message' in msg_obj
    assert msg_obj['message'] == 'a string'
    assert 'timestamp' in msg_obj

    # import pdb;pdb.set_trace()


def test_msg_pub_sub(msg_publisher, msg_subscriber):
    assess_pub_sub(msg_publisher, msg_subscriber)


def test_cmd_pub_sub(cmd_publisher, cmd_subscriber):
    assess_pub_sub(cmd_publisher, cmd_subscriber)
