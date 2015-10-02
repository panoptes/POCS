from .config import *
from .database import *
from . import error as error
from .logger import *
from .rs232 import *
from .modules import *

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
