import os
import shutil
import time

from astropy import units as u
from astropy.coordinates import AltAz
from astropy.coordinates import ICRS
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.utils import resolve_name


def current_time(flatten=False, datetime=False, pretty=False):
    """ Convenience method to return the "current" time according to the system.

    Note:
        If the ``$POCSTIME`` environment variable is set then this will return
        the time given in the variable. This is used for setting specific times
        during testing. Normal operating usage of POCS will clear the variable
        before starting.

    .. doctest::

        >>> os.environ['POCSTIME'] = '1999-12-31 23:59:59'
        >>> party_time = current_time(pretty=True)
        >>> party_time
        '1999-12-31 23:59:59'

        >>> del os.environ['POCSTIME']
        >>> from pocs.utils import current_time
        >>> now = current_time()
        >>> now
        <Time object: scale='utc' format='datetime' value=...>

        >>> now = current_time(datetime=True)
        >>> now
        datetime.datetime(...)

        >>> now = current_time(pretty=True)
        >>> now                               # doctest: +SKIP
        2018-09-28 00:14:18


    Returns:
        astropy.time.Time: Object representing now.
    """

    pocs_time = os.getenv('POCSTIME')

    if pocs_time is not None and pocs_time > '':
        _time = Time(os.getenv('POCSTIME'))
    else:
        _time = Time.now()

    if flatten:
        _time = flatten_time(_time)

    if pretty:
        _time = _time.isot.split('.')[0].replace('T', ' ')

    if datetime:
        # Add UTC timezone
        _time = _time.to_datetime()

    return _time


def flatten_time(t):
    """Given an astropy time, flatten to have no extra chars besides integers.

    .. doctest::

        >>> from astropy.time import Time
        >>> from pocs.utils import flatten_time
        >>> t0 = Time('1999-12-31 23:59:59')
        >>> t0.isot
        '1999-12-31T23:59:59.000'

        >>> flatten_time(t0)
        '19991231T235959'

    Args:
        t (astropy.time.Time): The time to be flattened.

    Returns:
        str: The flattened string representation of the time.
    """
    return t.isot.replace('-', '').replace(':', '').split('.')[0]


# This is a streamlined variant of PySerial's serialutil.Timeout.
class CountdownTimer(object):
    """Simple timer object for tracking whether a time duration has elapsed.


    Args:
        duration (int or float or astropy.units.Quantity): Amount of time to before time expires.
            May be numeric seconds or an Astropy time duration (e.g. 1 * u.minute).
    """

    def __init__(self, duration):
        if isinstance(duration, u.Quantity):
            duration = duration.to(u.second).value
        elif not isinstance(duration, (int, float)):
            raise ValueError(
                'duration (%r) is not a supported type: %s' % (duration, type(duration)))

        #: bool: True IFF the duration is zero.
        assert duration >= 0, "Duration must be non-negative."
        self.is_non_blocking = (duration == 0)

        self.duration = duration
        self.restart()

    def expired(self):
        """Return a boolean, telling if the timeout has expired.

        Returns:
            bool: If timer has expired.
        """
        return self.time_left() <= 0

    def time_left(self):
        """Return how many seconds are left until the timeout expires.

        Returns:
            int: Number of seconds remaining in timer, zero if ``is_non_blocking=True``.
        """
        if self.is_non_blocking:
            return 0
        else:
            delta = self.target_time - time.monotonic()
            if delta > self.duration:
                # clock jumped, recalculate
                self.restart()
                return self.duration
            else:
                return max(0, delta)

    def restart(self):
        """Restart the timed duration."""
        self.target_time = time.monotonic() + self.duration


def listify(obj):
    """ Given an object, return a list.

    Always returns a list. If obj is None, returns empty list,
    if obj is list, just returns obj, otherwise returns list with
    obj as single member.

    Returns:
        list:   You guessed it.
    """
    if obj is None:
        return []
    else:
        return obj if isinstance(obj, (list, type(None))) else [obj]


def get_free_space(dir=None):
    """Return the amoung of freespace in gigabytes for given dir.

    .. doctest::

        >>> from pocs.utils import get_free_space
        >>> get_free_space()
        <Quantity ... Gbyte>

    Args:
        dir (str, optional): Path to directory. If None defaults to $PANDIR.

    Returns:
        astropy.units.Quantity: The number of gigabytes avialable in folder.

    """
    if dir is None:
        dir = os.getenv('PANDIR')

    _, _, free_space = shutil.disk_usage(dir)
    free_space = (free_space * u.byte).to(u.gigabyte)
    return free_space


def load_module(module_name):
    """Dynamically load a module.

    .. doctest::

        >>> from pocs.utils import load_module
        >>> camera = load_module('pocs.camera.simulator')
        >>> camera.__package__
        'pocs.camera'

    Args:
        module_name (str): Name of module to import.

    Returns:
        module: an imported module name

    Raises:
        error.NotFound: If module cannot be imported.
    """
    from pocs.utils import error
    try:
        module = resolve_name(module_name)
    except ImportError:
        raise error.NotFound(msg=module_name)

    return module


def altaz_to_radec(alt=35, az=90, location=None, obstime=None, verbose=False):
    """Convert alt/az degrees to RA/Dec SkyCoord.

    Args:
        alt (int, optional): Altitude, defaults to 35
        az (int, optional): Azimute, defaults to 90 (east)
        location (None|astropy.coordinates.EarthLocation, required): A valid location.
        obstime (None, optional): Time for object, defaults to `current_time`
        verbose (bool, optional): Verbose, default False.

    Returns:
        astropy.coordinates.SkyCoord: Coordinates corresponding to the AltAz.
    """
    assert location is not None
    if obstime is None:
        obstime = current_time()

    if verbose:
        print("Getting coordinates for Alt {} Az {}, from {} at {}".format(
            alt, az, location, obstime))

    altaz = AltAz(obstime=obstime, location=location, alt=alt * u.deg, az=az * u.deg)
    return SkyCoord(altaz.transform_to(ICRS))
