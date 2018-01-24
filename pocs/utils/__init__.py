import os
import re
import shutil
import subprocess


from astropy import units as u
from astropy.coordinates import AltAz
from astropy.coordinates import ICRS
from astropy.coordinates import SkyCoord
from astropy.time import Time, TimezoneInfo
from astropy.utils import resolve_name


def current_time(flatten=False, datetime=False, pretty=False):
    """ Convenience method to return the "current" time according to the system

    If the system is running in a simulator mode this returns the "current" now for the
    system, which does not necessarily reflect now in the real world. If not in a simulator
    mode, this simply returns `current_time()`

    Returns:
        (astropy.time.Time):    `Time` object representing now.
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
        _time = _time.to_datetime(timezone=TimezoneInfo())

    return _time


def flatten_time(t):
    """ Given an astropy Time, flatten to have no extra chars besides integers """
    return t.isot.replace('-', '').replace(':', '').split('.')[0]


def listify(obj):
    """ Given an object, return a list

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
    if dir is None:
        dir = os.getenv('PANDIR')

    _, _, free_space = shutil.disk_usage(dir)
    free_space = (free_space * u.byte).to(u.gigabyte)
    return free_space


def list_connected_cameras():
    """
    Uses gphoto2 to try and detect which cameras are connected.
    Cameras should be known and placed in config but this is a useful utility.
    """

    gphoto2 = shutil.which('gphoto2')
    command = [gphoto2, '--auto-detect']
    result = subprocess.check_output(command)
    lines = result.decode('utf-8').split('\n')

    ports = []

    for line in lines:
        camera_match = re.match('([\w\d\s_\.]{30})\s(usb:\d{3},\d{3})', line)
        if camera_match:
            # camera_name = camera_match.group(1).strip()
            port = camera_match.group(2).strip()
            ports.append(port)

    return ports


def load_module(module_name):
    """ Dynamically load a module

    Returns:
        module: an imported module name
    """
    from pocs.utils import error
    try:
        module = resolve_name(module_name)
    except ImportError:
        raise error.NotFound(msg=module_name)

    return module


def altaz_to_radec(alt=35, az=90, location=None, obstime=None, *args, **kwargs):
    """ Convert alt/az degrees to RA/Dec SkyCoord

    Args:
        alt (int, optional): Altitude, defaults to 35
        az (int, optional): Azimute, defaults to 90 (east)
        location (None, required): A ~astropy.coordinates.EarthLocation
            location must be passed.
        obstime (None, optional): Time for object, defaults to `current_time`

    Returns:
        `astropy.coordinates.SkyCoord: FK5 SkyCoord
    """
    assert location is not None
    if obstime is None:
        obstime = current_time()

    verbose = kwargs.get('verbose', False)

    if verbose:
        print("Getting coordinates for Alt {} Az {}, from {} at {}".format(alt, az, location, obstime))

    altaz = AltAz(obstime=obstime, location=location, alt=alt * u.deg, az=az * u.deg)
    return SkyCoord(altaz.transform_to(ICRS))
