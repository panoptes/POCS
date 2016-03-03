import re
import os
import subprocess

from astropy.time import Time


def current_time(flatten=False, utcnow=False):
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


class PrintLog(object):

    """ Prints messages. Used as a simple replacement for no logger.

    Only prints if verbose is also True.

    Args:
        verbose(bool):  Determines if messages print or not. Defaults to True.
     """

    def __init__(self, verbose=True):
        self.verbose = verbose

        def printer(msg): self.print_msg(msg)

        for a in ['debug', 'info', 'warning', 'error']:
            setattr(self, a, printer)

    def print_msg(self, msg):
        if self.verbose:
            print(msg)
