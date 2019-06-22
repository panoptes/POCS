import os
import pytest
import yaml

from astropy import units as u

from pocs.utils.config import load_config
from panoptes.utils.config import save_config


def test_load_simulator(config):
    assert 'camera' in config['simulator']
    assert 'mount' in config['simulator']
    assert 'weather' in config['simulator']
    assert 'night' in config['simulator']


def test_overwrite(config):

    config01 = {
        'foo': 'bar'
    }
    config02 = {
        'bar': 'foo'
    }

    assert config01 != config02

    save_config('foo', config01)
    config03 = load_config('foo_local')

    assert config01 == config03

    save_config('foo', config02)
    config04 = load_config('foo')

    assert config02 == config04
    assert config01 != config04

    conf_fn = '{}/conf_files/foo_local.yaml'.format(os.getenv('POCS'))
    os.remove(conf_fn)
    assert os.path.exists(conf_fn) is False


def test_local_config():

    _local_config_file = '{}/conf_files/pocs_local.yaml'.format(os.getenv('POCS'))

    if not os.path.exists(_local_config_file):
        conf = load_config(ignore_local=True)
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
    _config_file = '{}/conf_files/pocs.yaml'.format(os.getenv('POCS'))
    _config_file_temp = '{}/conf_files/pocs_temp.yaml'.format(os.getenv('POCS'))
    os.rename(_config_file, _config_file_temp)

    config = load_config(ignore_local=True)

    assert len(config.keys()) == 0

    os.rename(_config_file_temp, _config_file)


def test_parse(config):
    lat = config['location']['latitude']
    assert isinstance(lat, u.Quantity)


def test_no_parse():
    config = load_config(parse=False, ignore_local=True)
    lat = config['location']['latitude']
    assert isinstance(lat, u.Quantity) is False
    assert isinstance(lat, str)  # "19.54 degree"


def test_location_latitude(config):
    lat = config['location']['latitude']
    assert lat >= -90 * u.degree and lat <= 90 * u.degree


def test_location_longitude(config):
    lat = config['location']['longitude']
    assert lat >= -360 * u.degree and lat <= 360 * u.degree


def test_location_positive_elevation(config):
    elev = config['location']['elevation']
    assert elev >= 0.0 * u.meter


def test_directories(config):
    assert config['directories']['data'] == os.path.join(os.getenv('PANDIR'), 'data')
