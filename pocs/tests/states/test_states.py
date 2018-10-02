import os
import pytest
from pocs.utils.messaging import PanMessaging


def test_housekeeping(pocs):

    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    assert pocs.is_safe() is True
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.observatory.current_observation is not None
    pocs.next_state = 'parking'
    assert pocs.goto_next_state()
    assert pocs.state == 'parking'
    assert pocs.observatory.current_observation is None
    assert pocs.observatory.mount.is_parked

    # No valid obs
    pocs.observatory.scheduler.clear_available_observations()

    # Since we don't have valid observations we will start sleeping for 30
    # minutes so send shutdown command first.
    pub = PanMessaging.create_publisher(6500)
    pub.send_message('POCS-CMD', 'shutdown')
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    assert pocs.goto_next_state()
    assert pocs.state == 'housekeeping'

    pocs.power_down()

    assert pocs.connected is False
    assert pocs.is_safe() is False


# Test variations on the PANID.
@pytest.fixture(scope='module', params=[None, 'INVALID', 'DELETEME', 'PAN000'])
def pan_id(request):
    return request.param


def test_housekeeping_panid_fail(pocs, pan_id):

    pocs.config['pan_id'] = pan_id

    if pan_id == 'DELETEME':
        del pocs.config['pan_id']

    if pan_id == 'NOBUCKET':
        del pocs.config['panoptes_network']['buckets']['images']

    pocs.config['panoptes_network']['image_storage'] = True

    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    assert pocs.is_safe() is True
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.observatory.current_observation is not None
    pocs.next_state = 'parking'
    assert pocs.goto_next_state()
    assert pocs.state == 'parking'
    assert pocs.observatory.current_observation is None
    assert pocs.observatory.mount.is_parked

    # No valid obs
    pocs.observatory.scheduler.clear_available_observations()

    # Since we don't have valid observations we will start sleeping for 30
    # minutes so send shutdown command first.
    pub = PanMessaging.create_publisher(6500)
    pub.send_message('POCS-CMD', 'shutdown')
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    assert pocs.goto_next_state()
    assert pocs.state == 'housekeeping'

    pocs.power_down()

    assert pocs.connected is False
    assert pocs.is_safe() is False
