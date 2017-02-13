#!/usr/bin/env python

import healpy as hp
import numpy as np
from matplotlib import pyplot as plt
import io
import os

from scipy.stats import norm
from astroquery.vizier import Vizier

from astropy.cosmology import WMAP9 as cosmo
from astropy.table import Column
import astropy.units as u
import astropy.constants as c

from matplotlib import colors
from threading import Timer
from astropy.time import Time

from astropy.coordinates import SkyCoord
from astropy.utils.data import download_file

from pocs.utils import current_time
from pocs.utils.too.horizon.horizon_range import Horizon
from pocs.utils.too.alert_pocs import Alerter
from pocs.utils.config import load_config

from astroplan import Observer
from astropy.coordinates import EarthLocation


class GravityWaveEvent():

    def __init__(self, fits_file, observer='', galaxy_catalog='J/ApJS/199/26/table3',
                 time='', key={'ra': '_RAJ2000', 'dec': '_DEJ2000'}, frame='fk5', unit='deg',
                 selection_criteria='', fov='', dist_cut=50.0, evt_attribs={}, test=False,
                 alert_pocs='', percentile=95.0, altitude='', configname='email_parsers',
                 tile_types='c_tr_tl_br_bl', *args, **kwargs):

        self.config_loc = load_config('pocs')
        self.verbose = kwargs.get('verbose', False)

        self.config_grav = load_config(configname)

        for parser in self.config_grav['email_parsers']:
            if parser['type'] == 'ParseGravWaveEmail':
                self.config_grav = parser

        if time == '':
            self.time = current_time()
        else:
            self.time = time

        if observer == '':

            longitude = self.config_loc['location']['longitude']
            latitude = self.config_loc['location']['latitude']
            elevation = self.config_loc['location']['elevation']
            name = self.config_loc['location']['name']
            timezone = self.config_loc['location']['timezone']

            self.observer = Observer(
                longitude=longitude,
                latitude=latitude,
                elevation=elevation,
                name=name,
                timezone=timezone)
        else:
            self.observer = observer

        if altitude == '':
            self.altitude = self.config_loc['location']['horizon']
        else:
            self.altitude = altitude

        self.horizon = Horizon(self.observer, self.altitude, time=self.time)

        if fov == '':
            self.fov = self.config_grav['inputs']['fov']
        else:
            self.fov = fov

        if selection_criteria == '':
            self.selection_crit = self.config_grav['inputs']['selection_criteria']
        else:
            self.selection_crit = selection_criteria

        if alert_pocs == '':
            self.alert_pocs = self.config_grav['inputs']['alert_pocs']
        else:
            self.alert_pocs = alert_pocs

        Vizier.ROW_LIMIT = -1
        self.catalog, = Vizier.get_catalogs(galaxy_catalog)
        self.event_data = download_file(fits_file, cache=True)
        self.key = key
        self.frame = frame
        self.unit = unit
        self.dist_cut = dist_cut
        self.evt_attribs = evt_attribs
        self.tile_types = tile_types

        if self.alert_pocs:
            self.alerter = Alerter()

        one_to_n = np.arange(len(self.catalog), dtype=np.int)
        idx = Column(name='index', data=one_to_n)
        bools = np.ones(len(self.catalog), dtype=bool)
        bools_colmn = Column(name='uncovered', data=bools)
        self.catalog.add_column(idx, index=0)
        self.catalog.add_column(bools_colmn, index=0)

        self.percentile = percentile
        self.test = test

    def define_tile(self, typ, candidate, ra_min, ra_max, dec_min, dec_max):
        '''defines a single tile given the edges andassigns it a center set of coordinates'''

        tile = {}

        name = ''
        try:
            name = self.evt_attribs['TRIGGER_NUM']
        except:
            name = ''

        tile['name'] = name + '_' + typ + '_on_' + str(candidate['SimbadName'])
        tile['ra_min'] = ra_min
        tile['ra_max'] = ra_max
        tile['dec_max'] = dec_max
        tile['dec_min'] = dec_min
        tile['center_ra'] = self.horizon.modulus(0.5 * (tile['ra_min'] + tile['ra_max']), 0.0, 360.0)
        tile['center_dec'] = self.horizon.modulus(0.5 * (tile['dec_min'] + tile['dec_max']), -90.0, 90.0)
        coords = SkyCoord(tile['center_ra'], tile['center_dec'], frame=self.frame, unit=self.unit)

        tile['name'] = name + '_' + str(coords.to_string('hmsdms'))
        return tile

    def define_tiles(self, candidate, types='c_tl_tr_bl_br'):
        '''Defines tiles around coordinates for specified types.

         candidate must be entry (row) from an Astropy table galaxy catalog.

         type: tl - top left, tr - top right, bl - bottom left, br - bottom right
         and c - centered. Separate using '_' '''

        ra = candidate[self.key['ra']]
        dec = candidate[self.key['dec']]
        coords = SkyCoord(ra, dec, frame=self.frame, unit=self.unit)

        top_left = {}
        top_right = {}
        bottom_left = {}
        bottom_right = {}
        centered = {}

        tiles = []

        left_ra_min = np.float64(ra - (0.005) * np.cos(coords.dec.to('radian')))
        left_ra_max = np.float64(
            ra + ((self.fov['ra'] - 0.005)) * np.cos(coords.dec.to('radian')))

        right_ra_min = np.float64(
            ra - ((self.fov['ra'] - 0.005)) * np.cos(coords.dec.to('radian')))
        right_ra_max = np.float64(
            ra + (0.005) * np.cos(coords.dec.to('radian')))

        top_dec_min = np.float64(dec + 0.005)
        top_dec_max = np.float64(dec - (self.fov['dec'] - 0.005))

        bottom_dec_min = np.float64(dec - 0.005)
        bottom_dec_max = np.float64(dec + (self.fov['dec'] - 0.005))

        if 'c' in types:

            ra_min = np.float64(
                ra - (self.fov['ra'] / 2) * np.cos(coords.dec.to('radian')))
            ra_max = np.float64(
                ra + (self.fov['ra'] / 2) * np.cos(coords.dec.to('radian')))
            dec_max = np.float64(dec + self.fov['dec'] / 2)
            dec_min = np.float64(dec - self.fov['dec'] / 2)
            centered = self.define_tile(
                'Centered', candidate, ra_min, ra_max, dec_min, dec_max)

            tiles.append(centered)

        if 'tl' in types:

            top_left = self.define_tile('Top Left', candidate, left_ra_min,
                                        left_ra_max, top_dec_min, top_dec_max)

            tiles.append(top_left)

        if 'tr' in types:

            top_right = self.define_tile('Top Right', candidate, right_ra_min, right_ra_max,
                                         top_dec_min, top_dec_max)

            tiles.append(top_right)

        if 'bl' in types:

            bottom_left = self.define_tile('Bottom Left', candidate, left_ra_min,
                                           left_ra_max, bottom_dec_min, bottom_dec_max)

            tiles.append(bottom_left)

        if 'br' in types:

            bottom_right = self.define_tile('Bottom Right', candidate, right_ra_min,
                                            right_ra_max, bottom_dec_min, bottom_dec_max)

            tiles.append(bottom_right)

        return tiles

    def get_tile_properties(self, cord, time, cands, prob):
        '''gets properties of time by counting all galaxies that fit in that tile'''

        tile = {}
        tile['gal_indexes'] = []
        center_coords = SkyCoord(float(cord['center_ra']),
                                 float(cord['center_dec']), 'fk5', unit='deg')

        try:
            index = cands['index']
        except Exception as e:
            if self.verbose:
                print('Catalog not indexed. Algorithm may not work properly. \
                         Index prior to calling this method for faster preformance.')
            one_to_n = np.arange(len(cands))
            idx = Column(name='index', data=one_to_n)
            cands.add_column(idx, index=0)

        keep = (self.catalog[self.key['ra']] <= cord['ra_max']) \
            & (self.catalog[self.key['ra']] >= cord['ra_min']) \
            & (self.catalog[self.key['dec']] <= cord['dec_max']) \
            & (self.catalog[self.key['dec']] >= cord['dec_min'])

        galaxies_in_tile = self.catalog[keep]
        tile['galaxies'] = []

        score = self.get_score_and_gals_in_tile(galaxies_in_tile, prob, tile, cord)

        tile['properties'] = {'name': 'GW_' + str(cord['name']),
                              'position': str(center_coords.to_string('hmsdms')),
                              'coords_num': [cord['center_ra'], cord['center_dec']],
                              'score': score,
                              'start_time': time,
                              'exp_time': self.get_exp_time(tile['galaxies']) * 60,
                              'mode': 'HDR',
                              'min_nexp': 1,
                              'exp_set_size': 1,
                              'min_mag': self.get_min_mag(),
                              'max_mag': self.get_max_mag(),
                              'priority': self.get_priority(score)}
        return tile

    def get_score_and_gals_in_tile(self, galaxies, prob, tile, cord):

        score = 0.0
        tile['text'] = "Galaxies in tile " + cord['name'] + ':\n'
        for gal in galaxies:
            if gal['uncovered']:

                cand_coords = SkyCoord(float(gal[self.key['ra']]),
                                       float(gal[self.key['dec']]), frame=self.frame, unit=self.unit)

                tile['text'] = tile['text'] + 'name: ' + \
                    str(gal['SimbadName']) + '   coords: ' + str(cand_coords.to_string('hmsdms')) + '\n'

                tile['gal_indexes'].append(gal['index'])

                if prob[gal['index']] == np.nan:
                    score = score
                else:
                    score = score + prob[gal['index']]

        return score

    def get_min_mag(self):
        return 10.0

    def get_max_mag(self):
        return 21

    def get_priority(self, score):
        '''To be expanded'''

        return 1000 + score * 10e3

    def get_exp_time(self, galaxies):
        '''To be filled in - need to calc exp time based on the least bright object.'''
        if self.test:
            return 1.0

        return 10.0

    def get_tile_cands(self, time, cands, prob):
        '''gets all tiles defined around all galaxies in the passed candidates,
           sets their properties and sets their exposure time, score, priority'''

        tile_cands = []
        max_score = {}
        max_score['score'] = []
        max_score['coords'] = []

        for indx, cand in enumerate(cands):

            if cand['uncovered']:

                perc = indx / len(cands)

                if perc % 10 == 0:
                    if self.verbose:
                        print('indexing... ' + str(perc) + '%')

                tiles = self.define_tiles(cand, types=self.tile_types)

                for tile in tiles:

                    tile = self.get_tile_properties(tile, time, cands, prob)

                    tile_cands.append(tile)

                    max_score['score'].append(tile['properties']['score'])
                    max_score['coords'].append(tile['properties']['coords_num'])

        return tile_cands, max_score

    def isnt_in(self, coords, covered_coords):
        '''checks if given set of coordinates is within the covered region in the current loop'''

        isnt_in = True

        if len(covered_coords) > 0:
            for cov_cord in covered_coords:
                if abs(coords[0] - cov_cord[0]) < self.fov['ra']:
                    if abs(coords[1] - cov_cord[1]) < self.fov['dec']:
                        isnt_in = False

        return isnt_in

    def get_good_tiles(self, cands, tile_cands, max_score,
                       tiles, time, sun_rise_time, alert_pocs=False):
        '''discriminates among all candidate tiles to only extract the ones with the maximum
           score and adds it to tiles to be observed.'''

        if len(tile_cands) > 0:
            max_scores = np.array(max_score['score'])
            max_scr = max(max_scores) * 0.10

            len_max = len(max_scores[max_scores >= max_scr])

            scores = np.array(max_score['score'])
            coords = np.array(max_score['coords'])
            indexes = np.argsort(-scores)
            scores = scores[indexes]
            coords = coords[indexes]
            tile_cands = np.array(tile_cands)
            tile_cands = tile_cands[indexes]

            sort = {'score': scores[:len_max], 'coords': coords[:len_max]}
            min_num = 10e-49
            if sort['score'][0] < min_num:
                return

            range_covered = []

            gal_indexes = []

            for tile in tile_cands:

                selection_criteria = self.selection_criteria(
                    tiles, cands, time, sun_rise_time)

                if not selection_criteria:

                    cords_cov = tile['properties']['coords_num']
                    scr = tile['properties']['score']

                    isnt_in = self.isnt_in(cords_cov, range_covered)

                    if scr in sort['score']:

                        if isnt_in:

                            tiles.append(tile)

                            # self.write_to_file(tile) <- does not work yet

                            if self.alert_pocs:

                                delta_t = self.delta_t(
                                    tile['properties']['start_time'])

                                self.alert_in_time(tile['properties'], delta_t)

                            if len(tile['gal_indexes']) > 0:
                                for ind in tile['gal_indexes']:
                                    if ind not in gal_indexes:
                                        gal_indexes.append(int(ind))
                            range_covered.append(
                                tile['properties']['coords_num'])

            galaxy_indexes = np.array(gal_indexes, dtype=np.int)

            self.catalog['uncovered'][galaxy_indexes] = False

    def alert_in_time(self, tile, time):

        t = Timer(time, self.alerter.send_alert, args=(
            True, self.evt_attribs['type'], tile))
        t.start()

    def delta_t(self, start_time):

        time_now = self.horizon.time_now()

        del_t = start_time - time_now
        if del_t.sec <= 0.0:
            return 0.0

        return del_t.sec

    def write_to_file(self, tile):

        with io.FileIO(str(tile['properties']['name']).replace(' ', '') + ".txt", "w") as f:
            f.write(tile['text'].decode('utf-8'))

    def selection_criteria(self, tiles, cands, time, sun_rise_time, num_loop=0):
        '''checks given selection criteria to see when we want to interrupt tiling.'''

        met = False

        if self.selection_crit['name'] == 'one_loop':
            if num_loop > 0:
                met = True
        elif self.selection_crit['name'] == 'observable_tonight':
            if time > sun_rise_time:
                met = True
        elif self.selection_crit['max_tiles'] == -1:
            if len(cands) == 0:
                met = True
        elif len(tiles) >= self.selection_crit['max_tiles']:
            met = True
        else:
            met = False

        return met

    def get_prob_red_dist(self, catalog, event_data):
        '''calculated the volume probability in the event map, the distance of galaxies
           in the catalog and the redshift of galaxies in the catalog.'''

        prob, distmu, distsigma, distnorm = hp.read_map(
            event_data, field=range(4))

        npix = len(prob)
        nside = hp.npix2nside(npix)
        pixarea = hp.nside2pixarea(nside)

        theta = 0.5 * np.pi - catalog[self.key['dec']].to('rad').value
        phi = catalog[self.key['ra']].to('rad').value
        ipix = hp.ang2pix(nside, theta, phi)

        z = self.get_redshift(catalog)
        r = self.get_dist_in_Mpc(z)

        dp_dV = prob[ipix] * distnorm[ipix] * \
            norm(distmu[ipix], distsigma[ipix]).pdf(r) / pixarea

        return dp_dV, z, r

    def get_redshift(self, catalog):
        '''calculates array of redshifts of all galxies in the catalog'''

        z = (u.Quantity(catalog['cz']) / c.c).to(u.dimensionless_unscaled)
        MK = catalog['Ktmag'] - cosmo.distmod(z)

        return z

    def get_dist_in_Mpc(self, redshift):
        '''calculates distance in Mpc of all galaxies in catalog'''

        r = cosmo.luminosity_distance(redshift).to('Mpc').value
        return r

    def non_empty_catalog(self, cands, time):
        '''makes sure list of galaxies we're looping over is non-empty'''

        zenith = self.horizon.zenith_ra_dec(time=time)
        horz_range = self.horizon.horizon_range(zenith=zenith)

        loop_cands = cands[(cands[self.key['ra']] > horz_range['min_ra']) &
                           (cands[self.key['ra']] < horz_range['max_ra']) &
                           (cands[self.key['dec']] > horz_range['min_dec']) &
                           (cands[self.key['dec']] < horz_range['max_dec'])]

        while len(loop_cands) == 0:
            time = time + 1.0 * u.minute

            zenith = self.horizon.zenith_ra_dec(time=time)
            horz_range = self.horizon.horizon_range(zenith=zenith)

            loop_cands = cands[(cands[self.key['ra']] > horz_range['min_ra']) &
                               (cands[self.key['ra']] < horz_range['max_ra']) &
                               (cands[self.key['dec']] > horz_range['min_dec']) &
                               (cands[self.key['dec']] < horz_range['max_dec'])]

        return loop_cands, time

    def tile_sky(self):
        '''tiles over the 95% region of the probability map, with distance gut
           given when initialized and the region observable tonight'''

        dp_dV, z, r = self.get_prob_red_dist(self.catalog, self.event_data)

        cands = self.catalog[(dp_dV >= np.nanpercentile(dp_dV, self.percentile)) & (r <= self.dist_cut) &
                             (self.catalog['uncovered'])]

        prob = dp_dV / max(dp_dV)
        prob[np.isnan(prob)] = 0

        tiles = []
        last_tile = 0
        start_time = self.horizon.start_time(self.time)
        [sun_set_time, sun_rise_time] = self.horizon.sun_set_rise()

        time = start_time

        loop_cands, time = self.non_empty_catalog(cands, time)

        num_loop = 0

        selection_criteria = self.selection_criteria(
            tiles, loop_cands, time, sun_rise_time, num_loop=num_loop)

        while not selection_criteria:
            num_loop = num_loop + 1
            if self.verbose:
                print(str(len(loop_cands)) + ' candidates left')
                print('we have ' + str(len(tiles)) + ' tiles.')

            tile_cands, max_score = self.get_tile_cands(
                time, loop_cands, prob)

            self.get_good_tiles(loop_cands, tile_cands,
                                max_score, tiles, time, sun_rise_time, alert_pocs=self.alert_pocs)

            delta_t = 0.0
            for tile in tiles[last_tile:-1]:

                exp_time = float(tile['properties']['exp_time'])

                if exp_time > delta_t:
                    delta_t = exp_time

            time = time + delta_t * u.minute
            cands = self.catalog[(dp_dV >= np.nanpercentile(dp_dV, self.percentile)) & (r <= self.dist_cut) &
                                 (self.catalog['uncovered'])]

            loop_cands, time = self.non_empty_catalog(cands, time)

            last_tile = len(tiles) - 1

            selection_criteria = self.selection_criteria(
                tiles, loop_cands, time, sun_rise_time, num_loop=num_loop)

        return tiles
