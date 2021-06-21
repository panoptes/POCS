# Test sensors.py ability to read from two sensor boards.

import pytest
import responses

from panoptes.pocs.sensor import remote
from panoptes.pocs.sensor import power
from panoptes.utils import error


@pytest.fixture
def remote_response():
    return {
        "data": {
            "source": "sleeping",
            "dest": "ready"
        },
        "type": "state",
        "_id": "1fb89552-f335-4f14-a599-5cd507012c2d"
    }


@pytest.fixture
def remote_response_power():
    return {
        "power": {
            "mains": True
        },
    }


@responses.activate
def test_remote_sensor(remote_response, remote_response_power):
    endpoint_url_no_power = 'http://192.168.1.241:8081'
    endpoint_url_with_power = 'http://192.168.1.241:8080'
    responses.add(responses.GET, endpoint_url_no_power, json=remote_response)
    responses.add(responses.GET, endpoint_url_with_power, json=remote_response_power)

    remote_monitor = remote.RemoteMonitor(
        sensor_name='test_remote',
        endpoint_url=endpoint_url_no_power,
        db_type='memory'
    )

    mocked_response = remote_monitor.capture(store_result=False)
    del mocked_response['date']
    assert remote_response == mocked_response

    # Check caplog for disconnect
    remote_monitor.disconnect()

    power_monitor = remote.RemoteMonitor(
        sensor_name='power',
        endpoint_url=endpoint_url_with_power,
        db_type='memory'
    )

    mocked_response = power_monitor.capture()
    del mocked_response['date']
    assert remote_response_power == mocked_response


def test_remote_sensor_no_endpoint():
    with pytest.raises(error.PanError):
        remote.RemoteMonitor(sensor_name='should_fail')


def test_power_board_no_device():
    """Attempt to find an arduino device, which should fail."""
    with pytest.raises(error.NotFound):
        power.PowerBoard()
