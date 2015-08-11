import pytest

from ..observatory import Observatory

from ..utils.config import load_config

config = load_config()

def test_no_config():
    """ Creates a blank Observatory """
    with pytest.raises(AssertionError):
        obs_1 = Observatory()

def test_default_config():
    """ Creates a default Observatory """
    obs_1 = Observatory(config=config)
