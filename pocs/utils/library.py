import ctypes
import ctypes.util

from pocs.utils import error


def load_library(name, path=None, mode=ctypes.DEFAULT_MODE, logger=None):
    """Utility function to load a shared/dynamically linked library (.so/.dylib/.dll).

    The name and location of the shared library can be manually specified with the library_path
    argument, otherwise the ctypes.util.find_library function will be used to try to locate based
    on library_name.

    Args:
        name (str): name of the library (without 'lib' prefix or any suffixes, e.g. 'fli').
        path (str, optional): path to the library e.g. '/usr/local/lib/libfli.so'.
        mode (int, optional): mode in which to load the library, see dlopen(3) man page for
            details. Should be one of ctypes.RTLD_GLOBAL, ctypes.RTLD_LOCAL, or
            ctypes.DEFAULT_MODE. Default is ctypes.DEFAULT_MODE.
        logger (logging.Logger, optional): logger to use.

    Returns:
        ctypes.CDLL

    Raises:
        pocs.utils.error.NotFound: raised if library_path not given & find_library fails to
            locate the library.
        OSError: raises if the ctypes.CDLL loader cannot load the library.
    """
    if mode is None:
        # Interpret a value of None as the default.
        mode = ctypes.DEFAULT_MODE
    # Open library
    if logger:
        logger.debug("Opening {} library".format(name))
    if not path:
        path = ctypes.util.find_library(name)
        if not path:
            raise error.NotFound("Cound not find {} library!".format(name))
    # This CDLL loader will raise OSError if the library could not be loaded
    return ctypes.CDLL(path, mode=mode)
