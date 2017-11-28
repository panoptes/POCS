import pytest
from astropy.coordinates import SkyCoord

from gunagala.imager import create_imagers

from pocs.utils import hdr


@pytest.fixture(scope='session')
def imagers():
    return create_imagers()


def test_target_list(imagers):
    name = 'M6 Toll'
    base = SkyCoord("16h52m42.2s -38d37m12s")

    for imager_name in imagers:
        targets = hdr.get_target_list(target_name=name,
                                      imagers=imagers,
                                      primary_imager=imager_name,
                                      base_position=base)


def test_target_list_bad(imagers):
    name = 'M6 Toll'
    base = SkyCoord("16h52m42.2s -38d37m12s")

    for imager_name in imagers:
        with pytest.raises(ValueError):
            targets = hdr.get_target_list(target_name=name,
                                          imagers=imagers,
                                          primary_imager=42,
                                          base_position=base)

    for imager_name in imagers:
        with pytest.raises(ValueError):
            targets = hdr.get_target_list(target_name=name,
                                          imagers=imagers,
                                          primary_imager=name,
                                          base_position=42)


def test_target_list_string(imagers):
    name = 'M6 Toll'
    base = "16h52m42.2s -38d37m12s"

    for imager_name in imagers:
        targets = hdr.get_target_list(target_name=name,
                                      imagers=imagers,
                                      primary_imager=imager_name,
                                      base_position=base)
