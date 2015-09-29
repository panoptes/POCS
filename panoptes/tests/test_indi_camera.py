import pytest

import astropy.units as u

from ..utils import indi as indi


def test_default():
    """ Creates a simply client, which will try to connect to the server """
    client = indi.PanIndi()

    assert client.devices is not None
