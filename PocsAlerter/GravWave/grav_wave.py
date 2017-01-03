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

from horizon_range import Horizon

horizon = Horizon()

class GravityWaveEvent():

	def __init__(self, fitz_file, galaxy_catalog = 'J/ApJS/199/26/table3',
				 location = horizon.location(), time = horizon.time_now(), tile_num = -1,
				 key = {'ra': '_RAJ2000', 'dec': '_DEJ2000'}, frame = 'fk5', unit = 'deg',
				 selection_crit = {'type': 'observable_tonight', 'max_tiles': 16}, fov = ['ra': 3.0, 'dec': 2.0]):

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
            top_left['center_ra'] = 0.5*(top_left['ra_min'] + top_left['ra_max'])
            top_left['center_dec'] = 0.5*(top_left['dec_min'] + top_left['dec_max'])

            tiles.append(top_left)
        if 'tr' in types:
        	top_right['name'] = 'Top Right on ' + str(candidate['SimbadName'])
            top_right['ra_max'] = right_ra_max
            top_right['ra_min'] = right_ra_min
            top_right['dec_max'] = top_dec_max
            top_right['dec_min'] = top_dec_min
            top_right['center_ra'] = 0.5*(top_right['ra_min'] + top_right['ra_max'])
            top_right['center_dec'] = 0.5*(top_right['dec_min'] + top_right['dec_max'])

            tiles.append(top_right)
        if 'bl' in types:
        	bottom_left['name'] = 'Bottom Left on ' + str(candidate['SimbadName'])
            bottom_left['ra_min'] = left_ra_min
            bottom_left['ra_max'] = left_ra_max
            bottom_left['dec_min'] = bottom_dec_min
            bottom_left['dec_max'] = bottom_dec_max
            bottom_left['center_ra'] = 0.5*(bottom_left['ra_min'] + bottom_left['ra_max'])
            bottom_left['center_dec'] = 0.5*(bottom_left['dec_min'] + bottom_left['dec_max'])

            tiles.append(bottom_left)
        if 'br' in types:
        	bottom_right['name'] = 'Bottom Right on ' + str(candidate['SimbadName'])
            bottom_right['ra_max'] = right_ra_max
            bottom_right['ra_min'] = right_ra_min
            bottom_right['dec_min'] = bottom_dec_min
            bottom_right['dec_max'] = bottom_dec_max
            bottom_right['center_ra'] = 0.5*(bottom_right['dec_min'] + bottom_right['dec_max'])
            bottom_right['center_dec'] = 0.5*(bottom_right['dec_min'] + bottom_right['dec_max'])

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

    def get_tile_properties(self, cord, ra_corr=self.ra_corr, cands=self.catalog,
    						 key=self.key, frame=self.frame, unit = self.unit):

    	tile = {}
        tile['gal_indexes'] = []
        center_coords = SkyCoord(float(cord['center_ra']), float(cord['center_dec']), 'fk5', unit='deg')

        tile['properties'] = {'name': cord['name'],
                              'coords': center_coords.to_string('hmsdms'),
                              'coords_num': [cord['center_ra'], cord['center_dec']],
                              'score': 0}

    	try:
    		index = cands['index']
    	except Exception as e:
    		print('Catalog not indexed. Algorithm may not work properly. \
    		 	  Index prior to calling this method for faster preformance.')
    		one_to_n = np.arange(len(cands))
        	idx = Column(name='index', data=one_to_n)
        	cands.add_column(idx, index=0)

    	keep = (ra_corr<=cord['ra_max']) & (ra_corr>=cord['ra_min']) & (cands[key['dec']]<=cord['dec_max']) & (cands[key['dec']]>=cord['dec_min'])
    	galaxies_in_tile = cands[keep]

    	tile['galaxies'] = []

    	for gal in galaxies_in_tile:

    		cand_coords = SkyCoord(float(gal[key['ra']]*np.cos(np.radians(gal[key['dec']]))),
    							   float(gal[key['dec']]), frame=frame, unit=unit)

            tile['galaxies'].append({'name': gal['SimbadName'],
                                     'coords': cand_coords.to_string('hmsdms'),
                                     'anything else': 'other stuff'})

            tile['gal_indexes'].append(gal['index'])

        tile['properties']['score'] = len(tile['galaxies'])

    def get_tile_cands(self, cands=self.catalog, ra_corr=self.ra_corr, selection_crit=self.selection_crit,
    					 key = self.key, frame = self.frame, unit = self.unit, fov = self.fov):

    	tile_cands = []
    	max_score = {}
    	max_score['score'] = []
    	max_score['coords'] = []

    	for cand, indx in cands:

    		if indx%100 == 0:
    			print('indexing... ', indx)

    		tiles = define_tiles(cand, key = key, frame = frame, unit = unit, fov = fov, types = 'tr_tl_br_bl_c')

    		for tile in tiles:

    			get_tile_properties(tile, ra_corr = ra_corr, cands = cands, frame = frame, unit = unit, key = key)

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


    def get_good_tiles(self, cands, tile_cands, max_score, tiles, selection_crit=self.selection_crit):

    	new_cands = cands
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

	    for tile in range(len(tile_cands)):

	        if len(tiles) < selection_crit['max_tiles']:

	            if tile['properties']['score'] in sort['score']
	            	and isnt_in(tile['properties']['coords_num'], range_covered, self.fov)==True:

	                tiles.append(tile)

	                if len(tile['gal_indexes']) > 0:
	                    for ind in tile['gal_indexes']:
	                        if ind not in gal_indexes:
	                            gal_indexes.append(ind)
	                range_covered.append(tile['properties']['coords_num'])

	            
	    galaxy_indexes = np.array(gal_indexes)
	    new_cands.remove_rows(galaxy_indexes[np.argsort(-galaxy_indexes)])

	    return new_cands

	def selection_criteria(self, selection_crit=self.selection_crit):

		met = 'not met'


	def get_prob(self, event_data=self.event_data):



	def get_r(self, event_data=self.event_data):


	def tile_sky(self, catalog=self.catalog, event_data=self.event_data, dist_cut = 50,
				 selection_crit=self.selection_crit):
    
		dp_dV = get_prob()

	    cands = catalog[(dp_dV >= np.nanpercentile(dp_dV,95)) & (r <= dist_cut)]
	    cands = cands[cands['_DEJ2000'] <= 18.0]
	    
	    tiles = []
	    loop_cands = cands
	    one_to_n = np.arange(len(loop_cands))
	    idx = Column(name='index', data=one_to_n)
	    loop_cands.add_column(idx, index=0)
	    while selection_criteria=='not met':
	        print(len(tiles))
	        print(str(len(loop_cands))+' candidates left')
	        
	        tile_cands, max_score = get_tile_cands(loop_cands)
	        
	        loop_cands = get_tiles(loop_cands, tile_cands, max_score, tiles)
	        
	        
	        
	        loop_cands.remove_column('index')
	        one_to_n = np.arange(len(loop_cands))
	        idx = Column(name='index', data=one_to_n)
	        loop_cands.add_column(idx, index=0)
	        
	    return tiles