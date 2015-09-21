from .config import *
from .database import *
from .error import *
from .logger import *
from .serial import *
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
    """ Prints messages. Used as a simple replacement for no logger """
    def __init__(self):
        printer = lambda x: print(x)

        for a in ['debug', 'info', 'warning', 'error']:
            setattr(self, a, printer)
