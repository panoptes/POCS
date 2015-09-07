from astropy.utils import resolve_name

def listify(obj):
    if obj is None:
        return []
    else:
        return obj if isinstance(obj, (list, type(None))) else [obj]

def load_module(module_name):
    """ Dynamically load a module

    TODO:
        Throw a custom error and deal with better.

    Returns:
        module: an imported module name
    """
    try:
        module = resolve_name(module_name)
    except ImportError as err:
        raise error.NotFound(msg=module_name)

    return module
