from astropy.utils import resolve_name

from ..utils import error


def load_module(module_name):
    """ Dynamically load a module

    TODO:
        Throw a custom error and deal with better.

    Returns:
        module: an imported module name
    """
    try:
        module = resolve_name(module_name)
    except ImportError:
        raise error.NotFound(msg=module_name)

    return module
