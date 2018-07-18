import os
import pytest
import uuid
import yaml

from astropy import units as u

from pocs.utils.config import load_config
from pocs.utils.config import save_config


def test_load_simulator(config):
    assert 'camera' in config['simulator']
    assert 'mount' in config['simulator']
    assert 'weather' in config['simulator']
    assert 'night' in config['simulator']


def test_no_overwrite(config):
    with pytest.warns(UserWarning):
        save_config('pocs', config, overwrite=False)


def test_overwrite(config):

    config01 = {
        'foo': 'bar'
    }
    config02 = {
        'bar': 'foo'
    }

    assert config01 != config02

    save_config('foo', config01)
    config03 = load_config('foo')

    assert config01 == config03

    save_config('foo', config02)
    config04 = load_config('foo')

    assert config02 == config04
    assert config01 != config04

    conf_fn = '{}/conf_files/foo.yaml'.format(os.getenv('POCS'))
    os.remove(conf_fn)
    assert os.path.exists(conf_fn) is False


def test_full_path():
    temp_config_path = '/tmp/{}.yaml'.format(uuid.uuid4())
    temp_config = {'foo': 42}
    save_config(temp_config_path, temp_config)

    c = load_config(temp_config_path)

    assert c == temp_config
    os.remove(temp_config_path)


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


def test_multiple_config():
    config01 = {'foo': 1}
    config02 = {'foo': 2, 'bar': 42}
    config03 = {'bam': 'boo'}

    assert config01 != config02

    f01 = str(uuid.uuid4())
    f02 = str(uuid.uuid4())
    f03 = str(uuid.uuid4())

    save_config(f01, config01)
    save_config(f02, config02)
    save_config(f03, config03)

    config04 = load_config(f01)
    config05 = load_config(f02)
    config06 = load_config(f03)

    assert config01 == config04
    assert config02 == config05
    assert config03 == config06

    config07 = load_config([f01, f02], ignore_local=True)
    config08 = load_config([f02, f01], ignore_local=True)

    assert config07 != config01
    assert config07 == config02

    assert config08 != config01
    assert config08 != config02
    assert config08 != config05

    assert 'foo' not in config06
    assert 'bar' not in config06
    assert 'foo' in config05
    assert 'foo' in config07
    assert 'foo' in config08
    assert 'bar' in config05
    assert 'bar' in config07
    assert 'bar' in config08
    assert 'bam' in config06

    assert config07['foo'] == 2
    assert config08['foo'] == 1

    os.remove('{}/conf_files/{}.yaml'.format(os.getenv('POCS'), f01))
    os.remove('{}/conf_files/{}.yaml'.format(os.getenv('POCS'), f02))
    os.remove('{}/conf_files/{}.yaml'.format(os.getenv('POCS'), f03))


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
    assert isinstance(lat, float)


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
    assert config['directories']['data'] == '{}/data'.format(os.getenv('PANDIR'))
