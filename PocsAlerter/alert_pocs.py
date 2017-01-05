#!/usr/bin/env python
# Import from folders
import sys
sys.path.append('$HOME/voevent-parse')
sys.path.append('$POCS/pocs/utils/')

# Import calculation helper methods
import math as m
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy import coordinates
from astropy import constants as const
from astroquery.simbad import Simbad

# Logging for reporting on how VO was parsed
import logging
logging.basicConfig(filename='script2.log',level=logging.INFO)
logger = logging.getLogger('notifier')
logger.handlers.append(logging.StreamHandler(sys.stdout))

# Import POCS messanger
from pocs.utils.messaging import PanMessaging as pm

# Import VO event parser and VO test event
import voeventparse as voevt
from voeventparse.tests.resources.datapaths import swift_bat_grb_pos_v2 as test_vo

from horizon_range import Horizon


class AlertPocs():

    def __init__(self, test=False, port_num=6500):
        self.sender = pm('publisher', port_num)
        self.test = test
        self.checked_targets = []


################################
# Parsing and Checking Methods #
################################

    def circular_radius_find_candidates(self, coords, error_rad):

        '''This method finds candidates in region of a circular radius around given coordinates.'''

        cands = []

        tbl = Simbad.query_region(coords, error_rad)

        length = len(tbl)

        for row in xrange(length):

            name = str(row['MAIN_ID'])
            coords = str(row['RA_s_ICRS']) + ' ' + str(tbl[j]['DEC_s_ICRS'])
            v = float(row['RV_VALUE'])
            obs_wavelength = str(row['GALDIM_WAVELENGTH'])
            typ = str(row['OTYPE'])

            cands.append({'name': name,
                            'coords': coords,
                            'frame': 'icrs',
                            'obs_wavelength': obs_wavelength,
                            'type': typ})

        return cands

    def trusted_channels(self):

        channels = ['ivo://nasa.gsfc.tan/gcn',
                     '']

        return channels

    def trusted_authors(self):

        authors = []

        return authors

    def is_trusted(self, channel, author):

        trusted = False

        channels = self.trusted_channels()
        authors = self.trusted_authors()

        if channel in channels or author in authors:

            trusted = True
            print("Channel or Author verified! Proceeding to check targets!")

        else:
            print("Channel or Author not verified! Will not send message.")

        return trusted

    def get_coords(self, c, unit, frm):

        if frm == 'ICRS':
            frame = 'icrs'
        else:
            frame = 'fk5'

        if unit == 'deg':
            co = SkyCoord(float(c[0]) * u.degree, float(c[1]) * u.degree, frame)
        elif unit == 'rad':
            co = SkyCoord(float(c[0]) * u.radian, float(c[1]) * u.radian, frame)

        co = co.transform_to('icrs')
        coords = co.to_string('hmsdms')

        return coords

    def get_time(self, t):

        return str(t)[0:19]

    def get_error(self, err, unit):

        error = err * u.degree

        if unit == 'deg':
            error = err * u.degree
        elif unit == 'rad':
            error = err*180/(2*m.pi) * u.degree

        return error

    def read_in_vo(self, name=''):

        if self.test == False:
            try:
                v = sys.stdin.read()
            except:
                v = name
        else:
            v = test_vo

        try:
            with open(v, 'rb') as f:
                vo = voevt.load(f)

        except FileNotFoundError:

            print('No File Found!')
            return None

        return vo

    # Modify to properly prioritize tiles
    def get_weights(self, target, typ):

         weight = {'ang': 1.0, 'redshift': 1.0, 'mag': 1.0}

         if 'nova' in typ:
              weight['mag'] = 0.1
         if 'GW' in typ or 'Grav' in typ or 'grav' in typ:
              weight['redshift'] = 2.0
              weight['ang'] = 0.5

         return weight

    def is_parsed_vo(self, vo):

        parsed = False
        attribs = {}

        try:
            attribs['name'] =  str(vo.Who.Author.shortName)
            if 'LVC' in attribs['name']:
                parsed, attribs = self.parse_grav_wave_evt(vo)

                return parsed, attribs

        except:
            return [parsed, attribs]

        try:
            attribs['citation'] = str(vo.Citations.EventIVORN.attrib['cite'])
        except:
            attribs['citation'] = ''

        try:
            c = voevt.pull_astro_coords(vo)
        except:
            c = [0, 0, 0, 0, 0]

        try:
            t = voevt.pull_isotime(vo)
        except:
            return [parsed, attribs]

        try:
            attribs['channel'] = str(vo.Who.AuthorIVORN)
        except:
            return [parsed, attribs]

        try:
            attribs['author'] = str(vo.Who.Author.contactEmail)
        except:
            return [parsed, attribs]

        try:
            attribs['type'] = str(vo.attrib['role'])
        except:
            attribs['type'] = None

        try:
            attribs['expiery_time'] = vo.Why.attrib['expires']
        except:
            attribs['expiery_time'] = 'WANT TO SET THIS TO SAME NIGHT'

        unit = str(c[3])
        system = str(c[4])
        attribs['error'] = self.get_error(float(c[2]), unit)
        attribs['coords'] = self.get_coords([float(c[0]), float(c[1])], unit, system)
        attribs['start_time'] = t

        parsed = True

        return parsed, attribs

##
    def append_cands(self, attribs):

        if attribs['error'] > 1.0*u.deg:

            candidates = self.find_candiadtes(attribs['coords'], attribs['error'])

            for candidate in candidates:

                if self.is_valid(candidate, 'none'):

                    object_name = candidate['name']
                    typ = candidate['type']
                    coords = candidate['coords']
                        
                    self.checked_targets.append({'target': object_name,
                                            'ToO_name': attribs['name'],
                                            'position': coords,
                                            'priority': '1000',
                                            'expires_after': '10',
                                            'rescan_interval': 'rescan_interval',
                                            'start_time': attribs['start_time'],
                                            'exp_time': '120',
                                            'author': attribs['author'],
                                            'channel': attribs['channel'],
                                            'type_of_ToO': attribs['type']})
        else:
            self.checked_targets.append({'target': attribs['name'],
                                    'ToO_name': attribs['name'],
                                    'position': attribs['coords'],
                                    'priority': '1000',
                                    'expires_after': '10',
                                    'rescan_interval': 'rescan_interval',
                                    'start_time': attribs['start_time'],
                                    'exp_time': '120',
                                    'author': attribs['author'],
                                    'channel': attribs['channel'],
                                    'type_of_ToO': attribs['type']})

##
    def is_target_available(self, vo):

        target_available = False

        is_parsed, attribs = self.is_parsed_vo(vo)

        if is_parsed == False:

            print("VO event could not be parsed. Missing information on name, \
                    channel, author, coordinates or start time.")

            return target_available, ''

        elif attribs['test'] == self.test:
            if self.is_trusted(attribs['channel'], attribs['author']) == True:

                self.append_cands(attribs)

                if len(self.checked_targets) > 0:

                    target_available = True

            elif 'LVC' in attribs['name'] or 'LIGO' in attribs['name']:

                grav_wave = GravityWaveEvent(attribs['fits_file'], time = attribs['time'],
                                             dist_cut = attribs['max_dist'], 
                                             selection_criteria = {'type': 'observable_tomight', 'max_tiles': 3000})

                self.checked_targets = grav_wave.tile_sky()
        else:
            if self.test == True:
                print('ERROR: You are configured for testing and this vo was not a test.')
            if self.test == False:
                print('POCS not alerted: This VO was a test.')

        if len(self.checked_targets) > 0:

            target_available = True
            citation = attribs['citation']
            if 'followup' in attribs['citation']:
                citation = followup
            elif 'Preliminary' in citation:
                citation = 'Preliminary'
            elif 'retraction' in citation:
                citation = 'retraction'

        return target_available, citation

##
    def alert_pocs(self, available, citation):

        if available == True:
            if citation == 'followup':
                sender.send_message('scheduler', {'message': 'modify', 'targets': checked_targets})
            elif citation == 'retraction':
                sender.send_message('scheduler', {'message': 'remove', 'targets': checked_targets})
            else:
                sender.send_message('scheduler', {'message': 'add', 'targets': checked_targets})

            print("Message sent: ", citation, " for targets: ", checked_targets)

        else:
            print('No target(s) found, POCS not alerted.')


    def parse_grav_wave_evt(self, vo):

        attribs = {}
        parsed = False
        try:
            attribs['name'] = vo.Who.contactName
        except:
            attribs['name'] = vo.Who.shortName
        try:
            attribs['email'] = vo.Who.contactEmail
        except:
            attribs['email'] = ''
        try:
            attribs['max_dist'] = vo.What.Param.attrib['Max_Distance']
        except:
            attribs['max_dist'] = 50.0
        try:
            attribs['test'] = False
            test1 = vo.What.Group.attrib['Trigger_ID'].Param.attrib['Test']
            test2 = vo.What.Group.attrib['Trigger_ID'].Param.attrib['Retraction']
            test3 = vo.What.Group.attrib['Trigger_ID'].Param.attrib['InternalTest']

            if any([test1, test2, test3] == True):
                attribs['test'] = True

        except:
            attribs['test'] = False
        try:
            attribs['time'] = vo.WhereWhen.ObsDataLocation.ObservationLocation.AstroCoords.Time.TimeInstant
        except:
            attribs['time'] = Horizon.time_now()
        try:
            attribs['citation'] = vo.Citations.EventIVORN.attrib['cite']
        except:
            attribs['citation'] = ''
        try:
            attribs['fits_file'] = vo.What.Param.attrib['SKYMAP_URL_FITS_?????'] # <- which protection are we under?
        except:
            print('ERROR: No fits fle found. Cannot parse event.')
            return False, attribs

        parsed = True

        return parsed, attribs



if __name__ == '__main__':
     
    vo = self.read_in_vo()
    is_target_available, citation = self.is_target_available(vo)

    self.alert_pocs(is_target_available, citation)

    
