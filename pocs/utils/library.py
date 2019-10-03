import ctypes
import ctypes.util

from pocs.utils import error


def load_library(name, path=None, logger=None):
    """Utility function to load a shared/dynamically linked library (.so/.dylib/.dll).

    The name and location of the shared library can be manually specified with the library_path
    argument, otherwise the ctypes.util.find_library function will be used to try to locate based
    on library_name.

    Args:
        name (str): name of the library (without 'lib' prefix or any suffixes, e.g. 'fli').
        path (str, optional): path to the library e.g. '/usr/local/lib/libfli.so'.

    Returns:
        ctypes.CDLL

    Raises:
        pocs.utils.error.NotFound: raised if library_path not given & find_libary fails to
            locate the library.
        OSError: raises if the ctypes.CDLL loader cannot load the library.
    """
    # Open library
    if logger:
        logger.debug("Opening {} library".format(name))
    if not path:
        path = ctypes.util.find_library(name)
        if not path:
            raise error.NotFound("Cound not find {} library!".format(name))
    # This CDLL loader will raise OSError if the library could not be loaded
    return ctypes.CDLL(path)
