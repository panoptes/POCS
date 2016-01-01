import re
import subprocess


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

        printer = lambda x: self.print_msg(x)

        for a in ['debug', 'info', 'warning', 'error']:
            setattr(self, a, printer)

    def print_msg(self, msg):
        if self.verbose:
            print(msg)
