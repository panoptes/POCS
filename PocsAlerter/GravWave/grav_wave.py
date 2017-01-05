#!/usr/bin/env python

import healpy as hp
import numpy as np
from matplotlib import pyplot as plt

from scipy.stats import norm
from astroquery.vizier import Vizier

from astropy.cosmology import WMAP9 as cosmo
from astropy.table import Column
import astropy.units as u
import astropy.constants as c
from matplotlib import colors

from astropy.coordinates import SkyCoord
from astropy.utils.data import download_file

from horizon_range import Horizon
from alert_pocs import PocsAlerter

horizon = Horizon()

class GravityWaveEvent():

	def __init__(self, fitz_file, galaxy_catalog = 'J/ApJS/199/26/table3',
				 location = horizon.location(), time = horizon.time_now(), tile_num = -1,
				 key = {'ra': '_RAJ2000', 'dec': '_DEJ2000'}, frame = 'fk5', unit = 'deg',
				 selection_crit = {'type': 'observable_tonight', 'max_tiles': 16}, 
				 fov = ['ra': 3.0, 'dec': 2.0], dist_cut = 50.0, evt_attribs = [],
				 alert_pocs=True):

		self.location = location
		self.time = time
		self.tile_num = tile_num
		Vizier.ROW_LIMIT = -1
		self.catalog, = Vizier.get_catalogs(galaxy_catalog)
		self.event_data = download_file(fitz_file, cache=True)
		self.ra_corr = self.catalog[key['ra']]*np.cos(np.radians(cands[key['dec']]))
		self.key = key
		self.frame = frame
		self.unit = unit
		self.selection_crit = selection_crit
		self.fov = fov
		self.dist_cut = dist_cut
		self.evt_attribs = evt_attribs
		self.alert_pocs = alert_pocs

		if alert_pocs == True:
			self.alerter = AlertPocs()


	def modulus(self, value, min_val, max_val):

		val = value

		if value < min_val:
			val = max_val - abs(value - min_val)
		elif value > max_val:
			val = min_val + abs(value - max_val)

		return val

	def define_tiles(self, candidate, key=self.key, frame=self.frame, unit=self.unit,
					 fov=self.fov, types='tl_tr_bl_br_c'):

		'''Defines tiles around coordinates for specified types.

		candidate must be entry (row) from an Astropy table galaxy catalog.

		type: tl - top left, tr - top right, bl - bottom left, br - bottom right
		and c - centered. Separate using '_' '''

		ra = candidate[key['ra']]
        dec = candidate[key['dec']]
        coords = SkyCoord(ra, dec, frame=frame, unit=unit)

		top_left = {}
		top_right = {}
		bottom_left = {}
		bottom_right = {}
		centered = {}

		tiles = []

		left_ra_min = np.float64((ra - 0.005)*np.cos(coords.dec.to('radian')))
		left_ra_max = np.float64((ra + (fov['ra']-0.005))*np.cos(coords.dec.to('radian')))

		right_ra_min = np.float64((ra - (fov['ra']-0.005))*np.cos(coords.dec.to('radian')))
		right_ra_max = np.float64((ra + 0.005)*np.cos(coords.dec.to('radian')))

		top_dec_min = np.float64(dec + 0.005)
		top_dec_max = np.float64(dec - (fov['dec']-0.005))

		bottom_dec_min = np.float64(dec - 0.005)
		bottom_dec_max = np.float64(dec + (fov['dec']-0.005))

		if 'tl' in types:
			top_left['name'] = 'Top Left on ' + str(candidate['SimbadName'])
            top_left['ra_min'] = left_ra_min
            top_left['ra_max'] = left_ra_max
            top_left['dec_max'] = top_dec_max
            top_left['dec_min'] = top_dec_min
            top_left['center_ra'] = self.modulus(0.5*(top_left['ra_min'] 
            									 + top_left['ra_max']), 0.0, 360.0)
            top_left['center_dec'] = self.modulus(0.5*(top_left['dec_min'] 
            									  + top_left['dec_max']), -90.0, 90.0)

            tiles.append(top_left)
        if 'tr' in types:
        	top_right['name'] = 'Top Right on ' + str(candidate['SimbadName'])
            top_right['ra_max'] = right_ra_max
            top_right['ra_min'] = right_ra_min
            top_right['dec_max'] = top_dec_max
            top_right['dec_min'] = top_dec_min
            top_right['center_ra'] = self.modulus(0.5*(top_right['ra_min'] 
            									  + top_right['ra_max']), 0.0, 360.0)
            top_right['center_dec'] = self.modulus(0.5*(top_right['dec_min']
            									   + top_right['dec_max']), -90.0, 90.0)

            tiles.append(top_right)
        if 'bl' in types:
        	bottom_left['name'] = 'Bottom Left on ' + str(candidate['SimbadName'])
            bottom_left['ra_min'] = left_ra_min
            bottom_left['ra_max'] = left_ra_max
            bottom_left['dec_min'] = bottom_dec_min
            bottom_left['dec_max'] = bottom_dec_max
            bottom_left['center_ra'] = self.modulus(0.5*(bottom_left['ra_min']
            										+ bottom_left['ra_max']), 0.0, 360.0)
            bottom_left['center_dec'] = self.modulus(0.5*(bottom_left['dec_min'] 
            										 + bottom_left['dec_max']), -90.0, 90.0)

            tiles.append(bottom_left)
        if 'br' in types:
        	bottom_right['name'] = 'Bottom Right on ' + str(candidate['SimbadName'])
            bottom_right['ra_max'] = right_ra_max
            bottom_right['ra_min'] = right_ra_min
            bottom_right['dec_min'] = bottom_dec_min
            bottom_right['dec_max'] = bottom_dec_max
            bottom_right['center_ra'] = self.modulus(0.5*(bottom_right['dec_min'] 
            										 + bottom_right['dec_max']), 0.0, 360.0)
            bottom_right['center_dec'] = self.modulus(0.5*(bottom_right['dec_min'] 
            										  + bottom_right['dec_max']), -90.0, 90.0)

            tiles.append(bottom_right)
        if 'c' in types:
        	centered['name'] = 'Centered on ' + str(candidate['SimbadName'])
            centered['ra_min'] = np.float64((ra - fov['ra']/2)*np.cos(coords.dec.to('radian')))
            centered['ra_max'] = np.float64((ra + fov['ra']/2)*np.cos(coords.dec.to('radian')))
            centered['dec_max'] = np.float64(dec + fov['dec']/2)
            centered['dec_min'] = np.float64(dec - fov['dec']/2)
            centered['center_ra'] = ra*np.cos(np.radians(dec))
            centered['center_dec'] = dec

            tiles.append(centered)

        return tiles

    def get_tile_properties(self, cord, time, ra_corr=self.ra_corr, cands=self.catalog,
    						 key=self.key, frame=self.frame, unit = self.unit):

    	tile = {}
        tile['gal_indexes'] = []
        center_coords = SkyCoord(float(cord['center_ra']),
        						 float(cord['center_dec']), 'fk5', unit='deg')

    	try:
    		index = cands['index']
    	except Exception as e:
    		print('Catalog not indexed. Algorithm may not work properly. \
    		 	  Index prior to calling this method for faster preformance.')
    		one_to_n = np.arange(len(cands))
        	idx = Column(name='index', data=one_to_n)
        	cands.add_column(idx, index=0)

    	keep = (ra_corr<=cord['ra_max']) \
    			& (ra_corr>=cord['ra_min']) \
    			& (cands[key['dec']]<=cord['dec_max']) \
    			& (cands[key['dec']]>=cord['dec_min'])

    	galaxies_in_tile = cands[keep]

    	tile['galaxies'] = []

    	for gal in galaxies_in_tile:

    		cand_coords = SkyCoord(float(gal[key['ra']]*np.cos(np.radians(gal[key['dec']]))),
    							   float(gal[key['dec']]), frame=frame, unit=unit)

            tile['galaxies'].append({'name': gal['SimbadName'],
                                     'coords': cand_coords.to_string('hmsdms'),
                                     'anything else': 'other stuff'})

            tile['gal_indexes'].append(gal['index'])

        tile['properties'] = {'name': cord['name'],
		                      'position': center_coords.to_string('hmsdms'),
		                      'coords_num': [cord['center_ra'], cord['center_dec']],
		                      'score': len(tile['galaxies']),
		                      'start_time': time,
		                      'exp_time': self.get_exp_time(tile['galaxies']),
		                      'exp_mode': 'HDR',
		                      'priority': self.get_priority(tile['galaxies'])}
        return tile

	def get_priority(self, galaxies):

		'''To be expanded'''

		return 1000 + len(galaxies)

	def get_exp_time(self, galaxies):

		'''To be filled in - need to calc exp time based on the least bright object.'''

		return 10*u.minute

    def get_tile_cands(self, time, cands=self.catalog, ra_corr=self.ra_corr,
    				   selection_crit=self.selection_crit, key = self.key,
    				   frame = self.frame, unit = self.unit, fov = self.fov):

    	tile_cands = []
    	max_score = {}
    	max_score['score'] = []
    	max_score['coords'] = []

    	for cand, indx in cands:

    		if indx%100 == 0:
    			print('indexing... ', indx)

    		tiles = define_tiles(cand, key = key, frame = frame,
    							 unit = unit, fov = fov, types = 'tr_tl_br_bl_c')

    		for tile in tiles:

    			tile = get_tile_properties(tile, time, ra_corr = ra_corr, cands = cands,
    							    frame = frame, unit = unit, key = key)

    			tile_cands.append(tile)

    	        max_score['score'].append(tile['properties']['score'])
                max_score['coords'].append(tile['properties']['coords_num'])

        return tile_cands, max_score

    def isnt_in(self, coords, covered_coords, fov = self.fov):

	    isnt_in = True

	    if len(covered_coords) > 0:
	        for cov_cord in covered_coords:
	            if abs(coords[0]-cov_cord[0]) <= fov['ra'] and abs(coords[1]-cov_cord[1]) <= fov['dec']:
	                isnt_in = False

	    return isnt_in


    def get_good_tiles(self, cands, all_cands, tile_cands, max_score,
    				   tiles, selection_crit=self.selection_crit, alert_pocs=False):

	    max_scores = np.array(max_score['score'])
	    len_max = len(max_scores[max_scores >= np.nanpercentile(max_scores, 98)])

	    scores = np.array(max_score['score'])
	    coords = np.array(max_score['coords'])
	    indexes = np.argsort(-scores)
	    scores = scores[indexes]
	    coords = coords[indexes]
	    tile_cands = np.array(tile_cands)
	    tile_cands = tile_cands[indexes]
	        
	    sort = {'score': scores[:len_max], 'coords': coords[:len_max]}

	    range_covered = []
	    gal_indexes = []

	    for tile in tile_cands:

	    	selection_criteria = self.selection_criteria(tiles, loop_cands, time, sun_rise_time, selection_crit)

	        if selection_criteria == 'not_met':

	            if tile['properties']['score'] in sort['score']
	            	and isnt_in(tile['properties']['coords_num'], range_covered, self.fov)==True:

	                tiles.append(tile['properties'])

	                if alert_pocs == True:
	                	self.alerter.alert_pocs(True, self.evt_attribs['type'], tiles)

	                if len(tile['gal_indexes']) > 0:
	                    for ind in tile['gal_indexes']:
	                        if ind not in gal_indexes:
	                            gal_indexes.append(ind)
	                range_covered.append(tile['properties']['coords_num'])

	            
	    galaxy_indexes = np.array(gal_indexes)
	    all_cands.remove_rows(galaxy_indexes[np.argsort(-galaxy_indexes)])

	    return all_cands

	def selection_criteria(self, tiles, cands, time, sun_rise_time, 
						   selection_crit=self.selection_crit):

		met = 'not met'
		if selection_crit['type'] == 'observable_tonight':
			if time > sun_rise_time:
				met = 'met'
		elif selection_crit['max_tiles'] == -1:
			if len(cands) == 0:
				met = 'met'
		elif:
			if len(tiles) > selection_crit['max_tiles']:
				met = 'met'
		return met

	def get_prob_red_dist(self, catalog = self.catalog, event_data=self.event_data, key= self.key):

		prob, distmu, distsigma, distnorm = hp.read_map(event_data, field=range(4))

		npix = len(prob)
		print(npix)
		nside = hp.npix2nside(npix)
		pixarea = hp.nside2pixarea(nside)

		theta = 0.5*np.pi - catalog[key['dec']].to('rad').value
		phi = catalog[key['ra']].to('rad').value
		ipix = hp.ang2pix(nside, theta, phi)

		z = self.get_redshift(catalog)
		r = self.get_dist_in_Mpc(z)

		dp_dV = prob[ipix]*distnorm[ipix]*norm(distmu[ipix], distsigma[ipix]).pdf(r) / pixarea

		return dp_dV, z, r

	def get_redshift(self, catalog=self.catalog):

		z = (u.Quantity(cat['cz']) / c.c).to(u.dimensionless_unscaled)
	    MK = cat['Ktmag'] - cosmo.distmod(z)
	    
	    return z

	def get_dist_in_Mpc(self, redshift):

		r = cosmo.luminosity_distance(redshift).to('Mpc').value
		return r

	def tile_sky(self, catalog = self.catalog, event_data = self.event_data, dist_cut = self.dist_cut,
				 selection_crit = self.selection_crit, key = self.key, alert_pocs=True):
    
		dp_dV, z, r = self.get_prob(catalog=catalog, event_data=event_data, key=key)

	    cands = catalog[(dp_dV >= np.nanpercentile(dp_dV,95)) & (r <= dist_cut)]
	    
	    tiles = []

	    one_to_n = np.arange(len(cands))
	    idx = Column(name='index', data=one_to_n)
	    cands.add_column(idx, index=0)

	    [sun_set_time, sun_rise_time] = horizon.sun_rise_set()

	    start_time = horizon.start_time(self.time)
	    time = start_time
	    zenith = horizon.zenith_ra_dec(time = start_time)
	    horz_range = horizon.horizon_range(zenith = zenith)

	    loop_cands = cands[(cands[key['ra']] > horz_range['min_ra']) \
	    					& (cands[key['ra']] < horz_range['max_ra']) \
	    					& (cands[key['dec']] > horz_range['min_dec']) \
	    					& (cands[key['dec']] < horz_range['max_dec'])]

	    selection_criteria = self.selection_criteria(tiles, loop_cands, time, sun_rise_time, selection_crit)

	    while selection_criteria=='not met':

	        print(len(tiles))
	        print(str(len(loop_cands))+' candidates left')

	        tile_cands, max_score = self.get_tile_cands(start_time, loop_cands)
	        
	        cands = self.get_good_tiles(loop_cands, cands, tile_cands, max_score, tiles, alert_pocs = alert_pocs)
	        
	        time = time + tiles[-1]['exp_time']
	       	zenith = horizon.zenith_ra_dec(time = time)
		    horz_range = horizon.horizon_range(zenith = zenith)
		    loop_cands = cands[(cands[key['ra']] > horz_range['min_ra']) \
		    					& (cands[key['ra']] < horz_range['max_ra']) \
		    					& (cands[key['dec']] > horz_range['min_dec']) \
		    					& (cands[key['dec']] < horz_range['max_dec'])]

	        selection_criteria = self.selection_criteria(tiles, loop_cands, time, sun_rise_time, selection_crit)

	    return tiles