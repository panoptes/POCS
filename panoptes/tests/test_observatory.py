import pytest

from ..observatory import Observatory


def test_no_config():
    """ Creates a blank Observatory """
    with pytest.raises(AssertionError):
        obs_1 = Observatory()
