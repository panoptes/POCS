import datetime
import yaml
import types
import numpy as np

import astropy.units as u
from astropy.coordinates import SkyCoord
import ephem


##----------------------------------------------------------------------------
##  Target Class
##----------------------------------------------------------------------------
class Target(object):
    """An object describing an astronomical target.

    An object representing a possible target which the scheduler is considering,
    also is the object which the scheduler will return when asked for a target
    to observe.
    """
    def __init__(self, dict):
        '''
        Takes in a dictionary describing the target as read from the YAML file.
        Populates the target properties from that dictionary.
        '''
        ## name
        assert 'name' in dict.keys():
        assert isinstance(dict['name'], str)
        self.name = dict['name']
        ## priority
        try:
            self.priority = float(dict['priority'])
        except:
            self.priority = 1.0
        ## position
        try:
            self.position = SkyCoord(dict['position'], dict['frame'])
        except:
            self.position = None
        ## equinox (assumes J2000 if unspecified)
        try:
            self.position.equinox = dict['equinox']
        except:
            self.position.equinox = 'J2000'
        ## equinox (assumes 2000 if unspecified)
        try:
            self.position.obstime = float(dict['epoch']
        except:
            self.position.obstime = 2000.
        ## proper motion (is tuple of dRA/dt dDec/dt)
        try:
            self.proper_motion = (dict['proper_motion'].split()[0], dict['proper_motion'].split()[1])
        except:
            self.proper_motion = (0.0, 0.0)
        ## visit
        self.visit = []
        obs_list = dict['visit']
        for obs_dict in obs_list:
            self.visit.append(Observation(obs_dict))


    def estimate_visit_duration(self, overhead=0*u.s):
    """Method to estimate the duration of a visit to the target.

        A quick and dirty estimation of the time it takes to execute the
        visit.  Does not currently account for overheads such as readout time,
        slew time, or download time.
        
        This function just sums over the time estimates of the observations
        which make up the visit.

    Args:
        overhead (astropy.units.Quantity): The overhead time for the visit in
        units which are reducible to seconds.  This is the overhead which occurs
        for each observation.

    Returns:
        astropy.units.Quantity: The duration (with units of seconds).
    """
        duration = 0*u.s
        for obs in self.visit:
            duration += obs.estimate_duration() + overhead
        return duration


##----------------------------------------------------------------------------
##  Observation Class
##----------------------------------------------------------------------------
class Observation(object):
    def __init__(self, dict):
    """An object which describes a single observation.

    Args:
        dict (dictionary): a dictionary describing the observation as read from
        the YAML file.
    """
        '''
        Takes in a dictionary describing the observation as read from the YAML
        file.  Populates the observation properties from that dictionary.
        '''
        ## master_exptime (assumes units of seconds, defaults to 120 seconds)
        try:
            self.master_exptime = dict['master_exptime'] * u.s
        except:
            self.master_exptime = 120 * u.s
        ## master_nexp (defaults to 1)
        try:
            self.master_nexp = int(dict['master_nexp'])
        except:
            self.master_nexp = 1
        ## master_filter
        try:
            self.master_filter = int(dict['master_filter'])
        except:
            self.master_filter = None
        ## analyze (defaults to False)
        try:
            self.analyze = dict['master_filter'] in ['True', 'true', 'Yes', 'yes', 'Y', 'y', 'T', 't']
        except:
            self.analyze = False

        ## slave_exptime (assumes units of seconds, defaults to 120 seconds)
        try:
            self.slave_exptime = dict['slave_exptime'] * u.s
        except:
            self.slave_exptime = 120 * u.s
        ## slave_nexp (defaults to 1)
        try:
            self.slave_nexp = int(dict['slave_nexp'])
        except:
            self.slave_nexp = 1
        ## slave_filter
        try:
            self.slave_filter = int(dict['slave_filter'])
        except:
            self.slave_filter = None


    def estimate_duration(self, overhead=0*u.s):
    """Method to estimate the duration of a ingle observation.

        A quick and dirty estimation of the time it takes to execute the
        observation.   Does not take overheads such as slewing, image readout,
        or image download in to consideration.

    Args:
        overhead (astropy.units.Quantity): The overhead time for the observation in
        units which are reducible to seconds.  This is the overhead which occurs
        for each exposure.

    Returns:
        astropy.units.Quantity: The duration (with units of seconds).
    """
        duration = max((self.master_exptime + overhead)*self.master_nexp,\
                       (self.slave_exptime + overhead)*self.slave_nexp)
        return duration


##----------------------------------------------------------------------------
##  Scheduler Class
##----------------------------------------------------------------------------
@logger.has_logger
@config.has_config
class Scheduler(object):
    """Summary line.

    Extended description of function.

    Args:
        arg1 (int): Description of arg1
        arg2 (str): Description of arg2

    Returns:
        bool: Description of return value

    """
    def get_target(self, weights={'observable': 100}):
    """Method which chooses the target to observe at the current time.

    This method examines a list of targets and performs a calculation to
    determine which is the most desirable target to observe at the current time.
    It constructs a merit value for each target which is a sum of one or more
    merit terms. The total merit value of an object is the sum of all the merit
    terms, each multiplied by a weighting factor for that term, then the sum is
    multiplied by the target's overall priority. This basic idea follows the
    general outline of the scheduler described by Denny (2004).

    Args:
        weights (dict): A dictionary whose keys are strings indicating the names
        of the merit functions to sum and whose values are the relative weights
        for each of those terms.

    Returns:
        Target: The chosen target object.
    """
        list_of_targets = self.get_target_list()
        merits = []
        for target in list_of_targets:
            vetoed = False
            target_merit = 0.0
            for term in weights.keys():
                term_function = getattr('term')
                merit_value = term_function(target)
                if merit_value and not vetoed:
                    target_merit += weights[term]*merit_value
                else:
                    vetoed = True
            if not vetoed:
                merits.append((target.priority*target_merit, target.name))
        return sorted(merits[0][1])


    def get_target_list(self, filename='default_targets.yaml'):
    """Reads the target database file and returns a list of target dictionaries.

    Args:
        filename (str): The YAML file to read the target information from.

    Returns:
        list: A list of dictionaries for input to the get_target() method.
    """
        yaml_list = yaml.load(filename)
        targets = []
        for target_dict in yaml_list:
            target = Target()
            targets.append()
        return targets


##----------------------------------------------------------------------------
## Merit Functions Are Defined Below
##----------------------------------------------------------------------------
def observable(target, observatory):
    """Merit function to evaluate if a target is observable.

    Args:
        target (Target): Target object to evaluate.
        observatory (Observatory): The observatory object for which to evaluate
        the target.

    Returns:
        1 or False: Returns False if the target is vetoed or returns 1 if not
        (a return value of 1 indicates that all elevations are equally
        meritorious).
    """
    assert isinstance(observatory, panoptes.observatory.Observatory)
    site = observatory.site
    assert isinstance(site, ephem.Observer)
    assert isinstance(target, Target)
    ephemdb = 'target,f|M|F7, {}, {},2.02,{},0'.format(\
                                                       target.position.ra.to_string(sep=':'),\
                                                       target.position.dec.to_string(sep=':'),\
                                                       target.position.epoch,\
                                                       )
    target = ephem.readdb(ephemdb)
    duration = target.estimate_visit_duration()

    ## Loop through duration of observation and see if any position is unobservable
    ## This loop is needed in case the shape of the horizon is complex and
    ## some values in between the starting and ending points are rejected even
    ## though the starting and ending points are ok.
    time_step = 30
    for dt in np.arange(0,int(duration.to(u.s).value)+time_step,time_step):
        time = starting_time + datetime.timedelta(0, dt)
        site.date = ephem.Date(time)
        target.compute(site)
        if not observatory.horizon(target.alt, target.az):
            return False
    ## Return 1 if no time steps returned False (unobservable)
    return 1
