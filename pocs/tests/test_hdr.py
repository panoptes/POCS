import pytest
import astropy.units as u
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
        for filter_name in imagers[imager_name].filters:
            exposure_parameters = {'filter_name': filter_name,
                                   'shortest_exp_time': 5 * u.second,
                                   'longest_exp_time': 600 * u.second,
                                   'num_long_exp': 1,
                                   'exp_time_ratio': 2.0,
                                   'snr_target': 5.0}
            targets = hdr.get_target_list(target_name=name,
                                          imagers=imagers,
                                          primary_imager=imager_name,
                                          base_position=base,
                                          exposure_parameters=exposure_parameters)


def test_target_list_bad(imagers):
    name = 'M6 Toll'
    base = SkyCoord("16h52m42.2s -38d37m12s")

    for imager_name in imagers:
        for filter_name in imagers[imager_name].filters:
            exposure_parameters = {'filter_name': filter_name,
                                   'shortest_exp_time': 5 * u.second,
                                   'longest_exp_time': 600 * u.second,
                                   'num_long_exp': 1,
                                   'exp_time_ratio': 2.0,
                                   'snr_target': 5.0}
            with pytest.raises(ValueError):
                targets = hdr.get_target_list(target_name=name,
                                              imagers=imagers,
                                              primary_imager=42,
                                              base_position=base,
                                              exposure_parameters=exposure_parameters)


def test_target_list_string(imagers):
    name = 'M6 Toll'
    base = "16h52m42.2s -38d37m12s"

    for imager_name in imagers:
        for filter_name in imagers[imager_name].filters:
            exposure_parameters = {'filter_name': filter_name,
                                   'shortest_exp_time': 5 * u.second,
                                   'longest_exp_time': 600 * u.second,
                                   'num_long_exp': 1,
                                   'exp_time_ratio': 2.0,
                                   'snr_target': 5.0}
            targets = hdr.get_target_list(target_name=name,
                                          imagers=imagers,
                                          primary_imager=imager_name,
                                          base_position=base,
                                          exposure_parameters=exposure_parameters)
