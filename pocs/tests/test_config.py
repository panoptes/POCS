import os
import pytest
import yaml

from astropy import units as u

from pocs.utils.config import load_config


@pytest.fixture
def conf():
    return load_config()


def test_load_simulator():
    conf = load_config(simulator=['all'])
    assert 'camera' in conf['simulator']
    assert 'mount' in conf['simulator']
    assert 'weather' in conf['simulator']
    assert 'night' in conf['simulator']


def test_local_config():

    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS'))

    if not os.path.exists(_local_config_file):
        conf = load_config()
        assert conf['name'] == 'Generic PANOPTES Unit'

        local_yaml = {
            'name': 'ConfTestName'
        }
        with open(_local_config_file, 'w') as f:
            f.write(yaml.dump(local_yaml))
        conf = load_config()
        assert conf['name'] != 'Generic PANOPTES Unit'
        os.remove(_local_config_file)
    else:
        conf = load_config()
        assert conf['name'] != 'Generic PANOPTES Unit'


def test_no_config():
    # Move existing config to temp
    _config_file = '{}/config.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _config_file_temp = '{}/config_temp.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    os.rename(_config_file, _config_file_temp)

    with pytest.raises(SystemExit):
        load_config()

    os.rename(_config_file_temp, _config_file)


def test_location_latitude(conf):
    lat = conf['location']['latitude']
    assert lat >= -90 * u.degree and lat <= 90 * u.degree


def test_location_longitude(conf):
    lat = conf['location']['longitude']
    assert lat >= -360 * u.degree and lat <= 360 * u.degree


def test_location_positive_elevation(conf):
    elev = conf['location']['elevation']
    assert elev >= 0.0 * u.meter


def test_directories(conf):
    assert conf['directories']['data'] == '{}/data'.format(os.getenv('PANDIR'))
