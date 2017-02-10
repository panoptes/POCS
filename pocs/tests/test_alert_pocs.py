import pytest
import os
from pocs.utils.too.alert_pocs import AlertPocs

from multiprocessing import Process

from astropy import units as u

from pocs import POCS
from pocs import _check_config
from pocs import _check_environment
from pocs.utils import error
from pocs.utils.config import load_config
from pocs.utils.database import PanMongo
from pocs.utils.messaging import PanMessaging


@pytest.fixture
def token_message():

    message = [{'coords': '0h0m0s 0d0m0s', 'name': 'Not an actual target',
                'priority': 0, 'exp_time': 0}]
    return message


def test_send_add_target_message(token_message):

    alerter = AlertPocs()
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'

    def start_pocs():
        pocs = POCS(simulator=['all'], messaging=True)
        pocs.initialize()
        pocs.observatory.scheduler.fields_list = [{'name': 'KIC 8462852',
                                                   'position': '20h06m15.4536s +44d27m24.75s',
                                                   'priority': '100',
                                                   'exp_time': 2,
                                                   'min_nexp': 1,
                                                   'exp_set_size': 1,
                                                   }]
        pocs.logger.info('Starting observatory run')
        pocs.run()
        assert len(pocs.observatory.scheduler.fields_list) == 2

    pocs_process = Process(target=start_pocs)
    pocs_process.start()

    sub = PanMessaging.create_subscriber(6511)
    pub = PanMessaging.create_publisher(6500)

    foo = True

    while foo is True:
        msg_type, msg_obj = sub.receive_message()
        if msg_type == 'STATUS':
            current_exp = msg_obj.get('observatory', {}).get('observation', {}).get('current_exp', 0)
            if current_exp >= 2:
                alerter.alert_pocs(True, 'add', token_message)
                pub.send_message('POCS-CMD', 'shutdown')
                foo = False

    pocs_process.join()
    assert pocs_process.is_alive() is False