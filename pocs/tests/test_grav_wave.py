import sys
sys.path.append('$POCS/PocsAlerter/GravWave')

import pytest
from pocs_alerter.grav_wave.grav_wave import GravityWaveEvent
from astropy.time import Time

@pytest.fixture
def sample_fits():
	return 'https://dcc.ligo.org/P1500071/public/10202_bayestar.fits.gz'

@pytest.fixture
def sample_time():

	time = Time()
	return time

def test_modulus_ra():

	grav_wave = GravityWaveEvent(sample_fits)
	pass

	min_val = 0.0
	max_val = 360.0

	val = 395.25

	val = grav_wave.modulus(val, min_val, max_val)

	assert (val <= max_val) and (val >= min_val)

def test_modulus_dec():

	grav_wave = GravityWaveEvent(sample_fits)

	min_val = -90.0
	max_val = 90.0

	val = -115.0

	val = grav_wave.modulus(val, min_val, max_val)

	assert (val <= max_val) and (val >= min_val)

def test_define_tiles_all():

	grav_wave = GravityWaveEvent(sample_fits)

	tiles = grav_wave.define_tiles(grav_wave.catalog[0], 'tl_tr_bl_br_c')

	assert len(tiles) == 5

def test_probability_redshift_calc():

	grav_wave = GravityWaveEvent(sample_fits)

	prob, redshift, dist = grav_wave.get_prob_red_dist(grav_wave.catalog, grav_wave.event_data)

	assert (len(prob) > 0) and (len(redshift) == len(dist)) and (len(prob) == len(dist))

def test_get_good_tiles():

	selection_criteria = {'type': '5_tiles', 'max_tiles': 5}

	grav_wave = GravityWaveEvent(sample_fits, percentile = 99.5, selection_criteria=selection_criteria)

	tiles = grav_wave.tile_sky(alert_pocs = False)

	max_score = 0

	for tile in tiles:

		if tile['properties']['score'] > max_score:
			max_score = tile['properties']['score']

	assert tiles[0]['properties']['score'] == max_score

def test_tile_sky():

	selection_criteria = {'type': '5_tiles', 'max_tiles': 5}

	grav_wave = grav_wave.GravityWaveEvent(sample_fits, percentile = 99.5, selection_criteria = selection_criteria)

	tiles = grav_wave.tile_sky(alert_pocs = False)

	assert len(tiles) == 5



