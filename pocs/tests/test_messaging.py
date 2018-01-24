import pytest
import time

from datetime import datetime
from multiprocessing import Process
from pocs.utils.messaging import PanMessaging


@pytest.fixture(scope='function')
def forwarder():
    def start_forwarder():
        PanMessaging.create_forwarder(12345, 54321)

    messaging = Process(target=start_forwarder)

    messaging.start()
    yield messaging
    messaging.terminate()


@pytest.fixture(scope='function')
def sub():
    messaging = PanMessaging.create_subscriber(54321)

    yield messaging
    messaging.close()


@pytest.fixture(scope='function')
def pub():
    messaging = PanMessaging.create_publisher(12345, bind=False, connect=True)
    time.sleep(2)  # Wait for publisher to start up
    yield messaging
    messaging.close()


# def test_publisher_receive(pub):
#     with pytest.raises(AssertionError):
#         pub.receive_message()


# def test_subscriber_send(sub):
#     with pytest.raises(AssertionError):
#         sub.send_message('FOO', 'BAR')


def test_forwarder(forwarder):
    assert forwarder.is_alive() is True


def test_messaging(forwarder, sub, pub):
    pub.send_message('TEST-CHANNEL', 'Hello')
    msg_type, msg_obj = sub.receive_message()

    assert msg_type == 'TEST-CHANNEL'
    assert isinstance(msg_obj, dict)
    assert 'message' in msg_obj
    assert msg_obj['message'] == 'Hello'


def test_send_datetime(forwarder, sub, pub):
    pub.send_message('TEST-CHANNEL', {
        'date': datetime(2017, 1, 1)
    })
    msg_type, msg_obj = sub.receive_message()
    assert msg_obj['date'] == '2017-01-01T00:00:00'


def test_mongo_objectid(forwarder, sub, pub, config, db):

    id0 = db.insert_current('config', {'foo': 'bar'}, store_permanently=False)

    pub.send_message('TEST-CHANNEL', db.get_current('config'))
    msg_type, msg_obj = sub.receive_message()
    assert '_id' in msg_obj
    assert isinstance(msg_obj['_id'], str)
    assert id0 == msg_obj['_id']
