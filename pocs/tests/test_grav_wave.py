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
