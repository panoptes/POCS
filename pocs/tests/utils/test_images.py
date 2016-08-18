import pytest

from pocs.utils.config import load_config
from pocs.utils.images import io

confg = load_config()


@pytest.skip
class TestImages():
    """ Test the image utils with a CR2 file """
    def test_crop_data():
        pass
