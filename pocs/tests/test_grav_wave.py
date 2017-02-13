import time

import os
from pocs.utils.too.alert_pocs import Alerter

from multiprocessing import Process

from astropy import units as u

from pocs import _check_config
from pocs import _check_environment
from pocs.utils import error
from pocs.utils.config import load_config
from pocs.utils.database import PanMongo
from pocs.utils.messaging import PanMessaging

import pytest
from pocs.utils.too.grav_wave.grav_wave import GravityWaveEvent
from pocs.utils.too.horizon.horizon_range import Horizon
from astropy.time import Time


@pytest.fixture
def sample_fits():
    return 'https://dcc.ligo.org/P1500071/public/10458_bayestar.fits.gz'


@pytest.fixture
def sample_time():

    time = Time()
    return time


@pytest.fixture
def configname():
    return 'email_parsers'


def test_define_tiles_all(sample_fits, configname):

    grav_wave = GravityWaveEvent(sample_fits, configname=configname, alert_pocs=False)

    tiles = grav_wave.define_tiles(grav_wave.catalog[0], 'tl_tr_bl_br_c')

    assert len(tiles) == 5


def test_probability_redshift_calc(sample_fits, configname):

    grav_wave = GravityWaveEvent(sample_fits, configname=configname, alert_pocs=False)

    prob, redshift, dist = grav_wave.get_prob_red_dist(grav_wave.catalog, grav_wave.event_data)

    assert (len(prob) > 0) and (len(redshift) == len(dist)) and (len(prob) == len(dist))


def test_get_good_tiles(sample_fits, configname):

    selection_criteria = {'name': 'one_loop', 'max_tiles': 5}

    grav_wave = GravityWaveEvent(sample_fits, percentile=99.5, selection_criteria=selection_criteria,
                                 alert_pocs=False, configname=configname)

    tiles = grav_wave.tile_sky()

    max_score = 0

    for tile in tiles:

        if tile['properties']['score'] > max_score:
            max_score = tile['properties']['score']

    assert tiles[0]['properties']['score'] == max_score


def test_tile_sky(sample_fits, configname):

    selection_criteria = {'name': '5_tiles', 'max_tiles': 5}

    grav_wave = GravityWaveEvent(sample_fits, percentile=99.5,
                                 selection_criteria=selection_criteria, alert_pocs=False, configname=configname)

    tiles = grav_wave.tile_sky()

    assert len(tiles) == 5

# def test_alerter_in_time(sample_fits, forwarder, sub):

#     def grav_wave_proc():

#         selection_criteria = {'name': '5_tiles', 'max_tiles': 5}
#         evt_attribs = {'type': 'Initial'}
#         grav_wave = GravityWaveEvent(sample_fits, test=True, selection_criteria=selection_criteria,
#                                      alert_pocs=True, evt_attribs=evt_attribs)

#         tiles = grav_wave.tile_sky()

#     #os.environ['POCSTIME'] = '2016-09-09 08:00:00'

#     pocs_time = Time('2016-09-09T08:00:00', format='isot', scale='utc')

#     horizon = Horizon(test = True)
#     pocs_time = horizon.time_now()
#     time_1 = horizon.time_now()

#     pocs_process = Process(target=grav_wave_proc)
#     pocs_process.start()

#     foo = True
#     count = 0
#     while foo is True and count < 5:

#         msg_type, msg_obj = sub.receive_message()

#         time_3 = horizon.time_now()
#         elapsed= time_3 - time_1
#         if elapsed.sec > 600.0:
#             foo = False

#         if msg_type == 'add_observation':
#                 time_2 = horizon.time_now()
#                 del_t = time_2 - time_1
#                 time = pocs_time + del_t
#                 count = count + 1
#                 for obj in msg_obj['targets']:
#                     assert obj['start_time'] < time

#     if foo is False:
#         assert count > 0
#     else:
#         assert foo is True
#     pocs_process.join()
#     assert pocs_process.is_alive() is False
