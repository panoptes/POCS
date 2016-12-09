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


class AlertPocs():

    def __init__(self, test=False, port_num=6500):
        self.sender = pm('publisher', port_num)
        self.test = test
        self.checked_targets = []


################################
# Parsing and Checking Methods #
################################
##
    # Possibly an outdated method - Need to replace py tiling algortithm
    def find_candidates(self, coords, error_rad):

        cands = []

        tbl = Simbad.query_region(coords, error_rad)

        length = len(tbl)

        for j in xrange(length - 1):

            name = str(tbl[j]['MAIN_ID'])
            coords = str(tbl[j]['RA_s_ICRS']) + ' ' + str(tbl[j]['DEC_s_ICRS'])
            v = float(tbl[j]['RV_VALUE'])
            obs_wavelength = str(tbl[j]['GALDIM_WAVELENGTH'])
            typ = str(tbl[j]['OTYPE'])

            if v != m.nan:
                redshift = m.sqrt((1 + v/c)/(1-v/c))
            else:
                redshift = m.inf

            cands.append({'name': name,
                            'coords': coords,
                            'redshift': redshift,
                            'obs_wavelength': obs_wavelength,
                            'type': typ})

        return cands

##
    def trusted_channels(self):

        channels = ['ivo://nasa.gsfc.tan/gcn',
                     '']

        return channels

##
    def trusted_authors(self):

        authors = []

        return authors

##
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

##
    # An outdated skeleton method - need to update with good prioritizing algorithm or
    # move to POCS
    def is_valid(self, target, type_of_evt):

         valid = False

         observable_crit = {'ang_resolution': 0.0, 'max_redshift': 1000, 'min_magnitude': 0}
         weight = self.get_weights(target, type_of_evt)

         size_diff = target['ang_size'] - observable_crit['ang_resolution']
         redshift_diff = observable_crit['max_redshift'] - target['redshift']
         magnitude_diff = target['magnitude'] - observable_crit['min_magnitude']

         weighted_sum = size_diff*weight['ang'] + redshift_diff*weight['redshift'] + magnitude_diff*weight['mag']

         if weighted_sum > 0:
              valid = True

         return valid

##
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

##
    def get_time(self, t):

        return str(t)[0:19]

##
    def get_error(self, err, unit):

        error = err * u.degree

        if unit == 'deg':
            error = err * u.degree
        elif unit == 'rad':
            error = err*180/(2*m.pi) * u.degree

        return error

##
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

##
    # Modify to be more expansive - possibly move into POCS
    def get_weights(self, target, typ):

         weight = {'ang': 1.0, 'redshift': 1.0, 'mag': 1.0}

         if 'nova' in typ:
              weight['mag'] = 0.1
         if 'GW' in typ or 'Grav' in typ or 'grav' in typ:
              weight['redshift'] = 2.0
              weight['ang'] = 0.5

         return weight

##
    def is_parsed_vo(self, vo):

        parsed = False
        attribs = {}

        try:
            attribs['citation'] = str(vo.Citations.EventIVORN.attrib['cite'])
        except:
            attribs['citation'] = ''

        try:
            c = voevt.pull_astro_coords(vo)
        except:
            return [parsed, attrribs]

        try:
            t = voevt.pull_isotime(vo)
        except:
            return [parsed, attribs]

        try:
            attribs['name'] =  str(vo.Who.Author.shortName)
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
            attribs['expiery_time'] = get_time(vo.Why.attrib['expires'])
        except:
            attribs['expiery_time'] = 'WANT TO SET THIS TO SAME NIGHT'

        unit = str(c[3])
        system = str(c[4])
        attribs['error'] = self.get_error(float(c[2]), unit)
        attribs['coords'] = self.get_coords([float(c[0]), float(c[1])], unit, system)
        attribs['start_time'] = self.get_time(t)

        parsed = True

        return parsed, attribs

##
    def append_cands(self, attribs):

        if attribs['error'] > 1 * u.degree:

            candidates = self.find_candiadtes(attribs['coords'], attribs['error'])

            for candidate in candidates:

                if self.is_valid(candidate, 'none'):

                   # exp_time = calc_exp_time(pixels, SNR)
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

        else:
            if self.is_trusted(attribs['channel'], attribs['author']) == True:

                self.append_cands(attribs)

                if len(self.checked_targets) > 0:

                    target_available = True

        return target_available, attribs['citation']

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


if __name__ == '__main__':
     
    vo = self.read_in_vo()
    is_target_available, citation = self.is_target_available(vo)

    self.alert_pocs(is_target_available, citation)

    
