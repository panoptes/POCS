import warnings

from pocs.utils.error import GoogleCloudError
from pocs.utils.google.storage import PanStorage


def is_authenticated():
    """Helper function to determine if authenticated to Google Cloud network.

    For information about authenticating, see:

    https://github.com/panoptes/POCS/tree/develop/pocs/utils/google

    Returns:
        bool: True if authenticated, False otherwise.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            PanStorage('test-bucket')

        return True
    except GoogleCloudError:
        return False
