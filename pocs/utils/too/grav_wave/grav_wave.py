#!/usr/bin/env python

import healpy as hp
import io
import numpy as np
import requests

from threading import Timer
from warnings import warn

from astroquery.vizier import Vizier
from scipy.stats import norm

from astropy import constants as c
from astropy import units as u
from astropy.coordinates import SkyCoord
from astropy.cosmology import WMAP9 as cosmo
from astropy.table import Column
from astropy.utils.data import download_file

from ....utils import current_time
from ....utils.config import load_config
from ....utils.too.alert_pocs import Alerter
from ....utils.too.horizon.horizon_range import Horizon

from astroplan import Observer


class GravityWaveEvent(object):

    def __init__(self, fits_file, observer=None, galaxy_catalog='J/ApJS/199/26/table3',
                 time=None, key={'ra': '_RAJ2000', 'dec': '_DEJ2000'}, frame='fk5', unit='deg',
                 selection_criteria=None, fov=None, dist_cut=50.0, evt_attribs={},
                 alert_pocs=None, percentile=95.0, altitude=None, configname='email_parsers',
                 tile_types='c_tr_tl_br_bl', *args, **kwargs):
        """Handles email-recieved gravity wave triggets.

        Reads probability map, applies it to a galaxy catalog and finds any number
        of optimal targets which provide the most coverage over the highest probability
        region of the probability map, but also attempt to cover the most galaxies.

        Attribs:
            - config_loc (dictionary): the config cointaining information about the observer's location.
            - config_grav (dictionary): the config cointaining info about the grav wave handler,
                including the field of view (fov) and the selection_criteria.
            - time (astropy.time.Time): start time of the event. Now, if input in None.
            - observer (astroplan.Observer): an observer with the location specified in the
                location config, unless observer ofjevt is given in the init.
            - altitude (float): the minimum altitude above the horizon where above which we want to be observing.
            - horizon (Horizon): has functions calculating the visible sky range from the observer.
            - fov (dictionary): of format {'ra': (float), 'dec': (float)}, info about the size of the field
                of view of the telescope. If not given, is read from config_grav
            - selection_criteria (dictionary): example: {'name': (srt), 'max_tiles': (float)}, determines
                when tiling is complete. If not provided, is read from config_grav.
            - alert_pocs (bool): tells the code whether or not to send alert of the targets.
            - catalog (astropy.table): is downloaded from Vizier. If name not provided, it loads the 2MASS Survey.
            - event_data (healpix map): probability map of the event downloaded from the fits_file.
            - key (dictionary): key for getting RA and DEC values out of catalog.
                Example: {'ra': (str), 'dec': (str)}.
            - frame (str): frame of coordinates in catalog.
            - unit (str): unit of coordiantes in catalog (deg, rad, ...)
            - dist_cut (float): the maximum distance to which we want to observe galaxies from catalog.
                Default is 50.0.
            - evt_attribs (dictionary): contains the attributes of the event in the trigger. Only one used is
                TRIGGER_NUM which tags the targets with the vent identifier.
            - tile_types (str): see define_tiles docstring for more details.
            - alerter (Alerter): used to send targets.
            - percentile (float): the percentile in which we want to select candidate galaxies from.
            - created_event (bool): False if there are exceptions raised downloading the catalog or probability map.
        """

        self.config_loc = load_config('pocs')
        self.verbose = kwargs.get('verbose', False)

        self.created_event = True

        self.config_grav = load_config(configname)

        for parser in self.config_grav['email_parsers']:
            if parser['type'] == 'GravWaveParseEmail':
                self.config_grav = parser

        if time is None:
            self.time = current_time()
        else:
            self.time = time

        if observer is None:

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

        if altitude is None:
            self.altitude = self.config_loc['location']['horizon']
        else:
            self.altitude = altitude

        self.horizon = Horizon(self.observer, self.altitude, time=self.time)

        if fov is None:
            self.fov = self.config_grav['inputs']['fov']
        else:
            self.fov = fov

        if selection_criteria is None:
            self.selection_crit = self.config_grav['inputs']['selection_criteria']
        else:
            self.selection_crit = selection_criteria

        if alert_pocs is None:
            self.alert_pocs = self.config_grav['inputs']['alert_pocs']
        else:
            self.alert_pocs = alert_pocs

        Vizier.ROW_LIMIT = -1
        try:
            self.catalog, = Vizier.get_catalogs(galaxy_catalog)
        except Exception as e:
            self.created_event = False
            if self.verbose:
                warn('Could not get catalog! Will not create event.')

        try:
            try:
                user = self.config_grav['inputs']['ligo_accname']
                password = self.config_grav['inputs']['ligo_password']
                requests.get(fits_file, auth=(user, password))
            except Exception as e:
                if self.verbose:
                    warn('Could not process login request for LIGO Collaboration.')

            self.event_data = download_file(fits_file, cache=True)

        except Exception as e:

            self.event_data = fits_file  # assumes fits file is a local file. FIX

            self.created_event = True  # assumes local file again. FIX
            if self.verbose:
                warn('Could not download probability map! Will not create event.')

        self.key = key
        self.frame = frame
        self.unit = unit
        self.dist_cut = dist_cut
        self.evt_attribs = evt_attribs
        self.tile_types = tile_types

        self.alerter = Alerter(**kwargs)

        one_to_n = np.arange(len(self.catalog), dtype=np.int)
        idx = Column(name='index', data=one_to_n)
        bools = np.ones(len(self.catalog), dtype=bool)
        bools_colmn = Column(name='uncovered', data=bools)
        self.catalog.add_column(idx, index=0)
        self.catalog.add_column(bools_colmn, index=0)

        self.percentile = percentile

    def define_tile(self, type_of_tile, candidate, ra_min, ra_max, dec_min, dec_max):
        """Defines a single tile.

        Defines a single tile given the edges and assigns it a center set of coordinates.

        Args:
            - type_of_tile (str): type of tile - centered, top_left, top_right, bottom_left or bottom_right.
            - candidate (entry in catalog): the candidate around which we're defining a tile.
            The following are there to make sure the center coordinates of the tile are not out of range
            of RA and Dec values:
                - ra_min (float)
                - dec_min (float)
                - ra_max (float)
                - dec_max (float)

        Returns:
            - skeleton tile as python dictionary - properties set in get_tile_properties."""

        tile = {}

        name = ''
        try:
            name = str(self.evt_attribs['TRIGGER_NUM'])
        except Exception as e:
            name = ''

        tile['name'] = name + '_' + type_of_tile + '_on_' + str(candidate['SimbadName'])
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
        """Defines tiles around coordinates for specified types.

         candidate must be entry (row) from an Astropy table galaxy catalog.

         type: tl - top left, tr - top right, bl - bottom left, br - bottom right
         and c - centered. Separate using '_'

        Args:
            - candidate (entry in galaxy catalog): candidate around which we define tiles.
            - types (str): see description above."""

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

    def get_tile_properties(self, coord, time, cands, prob):
        """Gets properties of time by counting all galaxies that fit in that tile.

        Args:
            - coord (dictionary): the skeleton tile defined in define_tiles.
            - time (astropy.time.Time): start time of event.
            - cands (astropy.table): all the candidates left after selection on map and loaction.
            - prob (list): the probability list corresponding to the lst of galaxies in the catalog.
        Returns:
            - tile (dictionary): tile with information about the contained galaxies,
                and properties relevant to observation."""

        tile = {}
        tile['gal_indexes'] = []
        center_coords = SkyCoord(float(coord['center_ra']),
                                 float(coord['center_dec']), 'fk5', unit='deg')

        if 'index' not in cands:
            if self.verbose:
                print('Catalog not indexed. Algorithm may not work properly. \
                         Index prior to calling this method for faster preformance.')
            one_to_n = np.arange(len(cands))
            idx = Column(name='index', data=one_to_n)
            cands.add_column(idx, index=0)

        keep = (self.catalog[self.key['ra']] <= coord['ra_max']) \
            & (self.catalog[self.key['ra']] >= coord['ra_min']) \
            & (self.catalog[self.key['dec']] <= coord['dec_max']) \
            & (self.catalog[self.key['dec']] >= coord['dec_min'])

        galaxies_in_tile = self.catalog[keep]
        tile['galaxies'] = []

        score = self.get_score_and_gals_in_tile(galaxies_in_tile, prob, tile, coord)

        tile['properties'] = {'name': 'GW_' + str(coord['name']),
                              'position': str(center_coords.to_string('hmsdms')),
                              'coords_num': [coord['center_ra'], coord['center_dec']],
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

    def get_score_and_gals_in_tile(self, galaxies, prob, tile, coord):
        """Gets the score of tile and galaxy information.

        Args:
            - galaxies (astropy table): all galaxies contained in tile.
            - prob (list): probability list corresponding to galaxies in catalog
            - tile (dictionary): the tile we're appending score and info about galaxies to.
            - coord (dictionary): the prototile, used here to get the title of the tile['text'].

        Returns:
            - score to append (float)."""

        score = 0.0
        tile['text'] = "Galaxies in tile " + coord['name'] + ':\n'
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
        """Gets minimum magnitude for observation in HDR.

        Needs further thought.

        Returns:
            10.0 (float)."""

        return 10.0

    def get_max_mag(self):
        """Gets maximum magnitude for observation in HDR.

        Needs urther thought.

        Returns:
            21.0 (float)"""

        return 21.0

    def get_priority(self, score):
        """Gets the priority of each tile for observation.

        To be expanded

        Args:
            - score of tile (float)
        Returns:
            1000 + tiles' score * 10e3"""

        return 1000 + score * 10e3

    def get_exp_time(self, galaxies):
        """Gets exposure time for each tile.

        Needs further thought.

        Args:
            - galaxies contained in tile.
        Returns:
            10.0 (float)"""

        return 10.0

    def get_tile_cands(self, time, cands, prob):
        """Gets all tile candidates for selection on catalog.

        Gets all tiles defined around all galaxies in the passed candidates,
           sets their properties and sets their exposure time, score, priority.

        Args:
            - time (astropy.time.Time): time where each tile starts to be visible.
            - cands (astropy table): candidates that were selected.
            - prob (list): list of probabilities corresponding to each galaxy.

        Returns:
            - tile_cands (list of dictionaries): list of all tiles around candidates in cands.
            - max_score (dictionary): contains positions and scores of all tiles
                - used for descriminating between candidates."""

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
        """Cheks that the tile isn't in a reagion already selected in this loop.

        Args:
            - coords (dictionary): the coordinates of the current tile.
            - covered_coords (list of dictionaries): all covered coordinates.

        Returns:
            - isnt_in (bool): True if the tile isn't in a region already observed. False if it is."""

        isnt_in = True

        if len(covered_coords) > 0:
            for cov_coord in covered_coords:
                if abs(coords[0] - cov_coord[0]) < self.fov['ra']:
                    if abs(coords[1] - cov_coord[1]) < self.fov['dec']:
                        isnt_in = False

        return isnt_in

    def get_good_tiles(self, cands, tile_cands, max_score,
                       tiles, time, sun_rise_time):
        """Gets best candidates out of all candidates.

        Discriminates among all candidate tiles to only extract the ones with the maximum
           score and adds it to tiles to be observed.

        Defines observed region. At start of call of method, it is empty. For each candidate
        tile, it checks to see if it's score is within 90% of the highest score stored
        in max_scores. If it is, we check if the tile is within the already observed region.
        If not, we append its coordinates to the observed reagion and append that tile to
        the tiles list. If it is, we do not append it to tiles. Every tile appended to tiles
        is sent as a target using the alerter if alert_pocs is True. The galaxies in every
        appended tile are marked as observed and are not considered in the selection in the next loop.

        Args:
            - cands (astropy table): all candidates that passed selection.
            - tile_cands (list of ddictionaries): all tile candidates.
            - max_score (dictionary): the second returned value in `get_tile_cands`
            - tiles (list): the list to which we append selected tiles.
            - time (astropy.time.Time): time at which tile_cands become observable
            - sun_rise_time (astropy.time.Time): sun rise time from current observer
        """

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

            tiles_to_send = []

            for tile in tile_cands:

                selection_criteria = self.selection_criteria(
                    tiles, cands, time, sun_rise_time)

                if not selection_criteria:

                    coords_cov = tile['properties']['coords_num']
                    scr = tile['properties']['score']

                    isnt_in = self.isnt_in(coords_cov, range_covered)

                    if scr in sort['score']:

                        if isnt_in:

                            tiles.append(tile)

                            # self.write_to_file(tile) <- does not work yet

                            if self.alert_pocs:

                                tiles_to_send.append(tile['properties'])

                            if len(tile['gal_indexes']) > 0:
                                for ind in tile['gal_indexes']:
                                    if ind not in gal_indexes:
                                        gal_indexes.append(int(ind))
                            range_covered.append(
                                tile['properties']['coords_num'])

            if self.alert_pocs:

                delta_t = self.delta_t(tiles_to_send[-1]['start_time'])

                if self.verbose:
                    print("Sent tiles: {} {} seconds".format(delta_t, tiles_to_send))
                self.alert_in_time(tiles_to_send, delta_t)

            galaxy_indexes = np.array(gal_indexes, dtype=np.int)

            self.catalog['uncovered'][galaxy_indexes] = False

    def alert_in_time(self, tiles, time):
        """Creates a time delay for sending event via alerter.

        Alerter sends the message only at the start time of each tile.

        Args:
            - tiles (list of dictionaries): targets to be sent
            - time (float): time in seconds that we need to wait until sending the alert."""

        for tile in tiles:
            tile['start_time'] = '{}'.format(tile['start_time'])
        t = Timer(time, self.alerter.send_alert, args=(self.evt_attribs['type'], tiles))
        t.start()

    def delta_t(self, start_time):
        """Calculates time delay between now and start time of each tile.

        Args:
            start_time (astropy.time.Time): start time of tile.
        Returns:
            del_t (float): time in seconds which we need to wait until sending the alert.
            0.0 if current_time > start_time"""

        time_now = current_time()

        del_t = start_time - time_now
        if del_t.sec <= 0.0:
            return 0.0

        return del_t.sec

    def write_to_file(self, tile):
        """Creates txt file containing all galaxies in each tile.

        Args:
            - tile (dictionary): tile whose galaxy contents we're printing
        """

        with io.FileIO(str(tile['properties']['name']).replace(' ', '') + ".txt", "w") as f:
            f.write(tile['text'].decode('utf-8'))

    def selection_criteria(self, tiles, cands, time, sun_rise_time, num_loop=0):
        """Checks if we've met selection criteria.

        The selection criteria is a dict with a 'name' and 'max_tiles' keys.
        If the name is 'observable_tonight', it will ignore max_tiles and will only
        return True (criteria met) if current time > sun rise time.
        If the name is 'one_loop', it will only do one main selection loop and return
        any number of tiles found within it.
        Otherwise, it will loop until we have the number of tiles specified in 'max_tiles'.

        Args:
            - tiles (list of dictionaries): all tiles tagged for observation thus far.
            - cands (astrpy table): the current list of candidates after selection.
            - time (astrpy.time.Time): the start time of most recent tile(s).
            - sun_rise_time (astropy.time.Time): time of sun rise.
            - num_loop (int): the number of main loops. Only used when checking
                selection criteria in the main loop.
        Returns:
            - met (bool): True if criteria met, False if not met."""

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
        """Calculates probability list, redshift and distance for each galaxy in catalog.

        Args:
            - catalog (astropy.table): full catalog with no selections on it.
            - event_data (healpix map): probability distribution for each galaxy.

        Returns:
            - dp_dV (list): probability wrt valume corresponding to each galaxy in the catalog
            - z (list): the redshift corresponding to each galaxy in catalog
            - r (list): distances in Mpc corresponding to each galaxy in catalog."""

        prob, distmu, distsigma, distnorm = hp.read_map(event_data, field=range(4))

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
        """Calculates redshifts for all galaxies in catalog.

        Args:
            - catalog (astropy table): full catalog with no selections made on it.
        Returns:
            - list of redshift values corresponding to all galaxies in catalog."""

        z = (u.Quantity(catalog['cz']) / c.c).to(u.dimensionless_unscaled)

        return z

    def get_dist_in_Mpc(self, redshift):
        """Calculates distance in Mpc for all galaxies in catalog.

        Args:
            - redshift (list): the redshift list returned by get_redshift
        Returns:
            - list of distances (as floats) in Mpc corresponding to all galaxies in catalog."""

        r = cosmo.luminosity_distance(redshift).to('Mpc').value
        return r

    def non_empty_catalog(self, cands, time):
        """Returns the first non-empty sub-catalog after applying selections.

        Args:
            - cands (astropy.table): catalog that has been selected on with the probability
                map and distance cut.
            - time (astropy.time.Time): start time of event.
        Returns:
            - loop_cands (astropy.table): the firt non-empty subcatalog.
            - time (astropy.time.Time): time at which the first non-empty subcatalog
                is visible from the observer in Horizon."""

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
        """Tiles over sky until selection criteria met.

        Applies distance, probability and location cuts on the map so that the
        tiles we recieve are the ones observable soonest after the start time
        of the event from the location in the Horizon class.

        The time in the loop incriments in exposure times of tile with the longest
        exposure time in the loop. For example, if the loop gave three tiles, with
        10.0, 11.0 and 5.0 exposure times, the time when the next loop starts will
        be time of pervious loop start + 11.0 minutes.

        Returns:
            - tiles (list of dictionaries): final targets, as per selection criteria."""

        dp_dV, z, r = self.get_prob_red_dist(self.catalog, self.event_data)

        cands = self.catalog[(dp_dV >= np.nanpercentile(dp_dV, self.percentile)) &  # cuts on percentile
                             (r <= self.dist_cut) &                                # cuts on distance
                             (self.catalog['uncovered'])]                          # only keeps galaxies
        # marked as unobserved.

        prob = dp_dV / max(dp_dV)  # normalizes probability list
        prob[np.isnan(prob)] = 0.0  # sets all nan entries to 0.0

        tiles = []  # defnes list of files to be observed
        last_tile = 0
        start_time = self.horizon.start_time(self.time)
        [sun_set_time, sun_rise_time] = self.horizon.observer.tonight()

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
                                max_score, tiles, time, sun_rise_time)

            delta_t = 0.0
            for tile in tiles[last_tile:-1]:

                exp_time = float(tile['properties']['exp_time'])

                if exp_time > delta_t:
                    delta_t = exp_time

            time = time + delta_t * u.minute

            # same cuts have to be appled as initially because our field of view changes.
            cands = self.catalog[(dp_dV >= np.nanpercentile(dp_dV, self.percentile)) &
                                 (r <= self.dist_cut) &
                                 (self.catalog['uncovered'])]

            loop_cands, time = self.non_empty_catalog(cands, time)

            last_tile = len(tiles) - 1

            selection_criteria = self.selection_criteria(
                tiles, loop_cands, time, sun_rise_time, num_loop=num_loop)

        return tiles
