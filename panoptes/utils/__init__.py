from .config import *
from .database import *
from .error import *
from .logger import *
from .io import *
from .modules import *

def listify(obj):
    if obj is None:
        return []
    else:
        return obj if isinstance(obj, (list, type(None))) else [obj]
