import os
import re
import subprocess

from astropy.time import Time
from astropy.utils import resolve_name

from ..utils import error


def current_time(flatten=False, utcnow=False, pretty=False):
    """ Convenience method to return the "current" time according to the system

    If the system is running in a simulator mode this returns the "current" now for the
    system, which does not necessarily reflect now in the real world. If not in a simulator
    mode, this simply returns `current_time()`

    Returns:
        (astropy.time.Time):    `Time` object representing now.
    """

    _time = Time.now()

    if os.getenv('POCSTIME') is not None:
        _time = Time(os.getenv('POCSTIME'))

    if flatten:
        _time = _time.isot.replace('-', '').replace(':', '').split('.')[0]

    if pretty:
        _time = _time.isot.split('.')[0].replace('T', ' ')

    if utcnow:
        _time = _time.datetime.utcnow()

    return _time


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


def list_connected_cameras():
    """
    Uses gphoto2 to try and detect which cameras are connected.
    Cameras should be known and placed in config but this is a useful utility.
    """

    command = ['gphoto2', '--auto-detect']
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
    try:
        module = resolve_name(module_name)
    except ImportError:
        raise error.NotFound(msg=module_name)

    return module
