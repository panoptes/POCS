import sys
sys.path.append('$POCS/PocsAlerter/GravWave')
import time

import os
from pocs_alerter.alert_pocs import AlertPocs

from multiprocessing import Process

from astropy import units as u

from pocs import POCS
from pocs import _check_config
from pocs import _check_environment
from pocs.utils import error
from pocs.utils.config import load_config
from pocs.utils.database import PanMongo
from pocs.utils.messaging import PanMessaging

from pocs_alerter.grav_wave.grav_wave import GravityWaveEvent
from pocs_alerter.horizon.horizon_range import Horizon
from astropy.time import Time

def forwarder():
    def start_forwarder():
        PanMessaging('forwarder', (6500, 6500))

    messaging = Process(target=start_forwarder)

    messaging.start()
    yield messaging
    messaging.terminate()

def sub():
    messaging = PanMessaging('subscriber', 6500)

    yield messaging
    messaging.subscriber.close()


def grav_wave_proc():
    sample_fits = 'https://dcc.ligo.org/P1500071/public/10458_bayestar.fits.gz'
    selection_criteria = {'name': '5_tiles', 'max_tiles': 15}
    evt_attribs = {'type': 'Initial'}
    grav_wave = GravityWaveEvent(sample_fits, test=True, selection_criteria=selection_criteria,
                                 alert_pocs=True, evt_attribs=evt_attribs)

    tiles = grav_wave.tile_sky()

    for tile in tiles:
    	print(tile['properties'])

if __name__ == '__main__':

    forwarder = forwarder()


    os.environ['POCSTIME'] = '2016-09-09 08:00:00'

    pocs_time = Time('2016-09-09T08:00:00', format='isot', scale='utc')

    horizon = Horizon(test = True)
    pocs_time = horizon.time_now()
    sub = sub()

    time_1 = horizon.time_now()

    pocs_process = Process(target=grav_wave_proc)
    pocs_process.start()

    foo = True
    count = 0
    while foo is True and count < 5:

        msg_type, msg_obj = sub.receive_message()

        time_3 = horizon.time_now()
        elapsed= time_3 - time_1
        if elapsed.sec > 600.0:
            foo = False
            print('Overtime')

        if msg_type == 'add_observation':
                time_2 = horizon.time_now()
                del_t = time_2 - time_1
                time = pocs_time + del_t
                count = count + 1
                for obj in msg_obj['targets']:
                    assert obj['start_time'] < time
                print('Got a message')

    if foo is False:
        assert count > 0
    else:
        assert foo is True
    pocs_process.join()
    assert pocs_process.is_alive() is False