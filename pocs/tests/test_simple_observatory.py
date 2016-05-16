import pytest

from ..observatory import Observatory

def test_no_config():
    """ Creates an Observatory without a config file. We expect this to
    fail with an AssertionError because an Observatory requires a config.
     """
    with pytest.raises(AssertionError):
        obs_1 = Observatory()
