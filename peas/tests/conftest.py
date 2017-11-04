import os
import pytest

from pocs.utils.config import load_config
from pocs.utils.data import download_all_files
from pocs.utils.database import PanMongo

try:
    download_all_files()
except Exception as e:
    pass


def pytest_addoption(parser):
    parser.addoption("--hardware-test", action="store_true", default=False, help="Test with hardware attached")


@pytest.fixture
def hardware_test(request):
    return request.config.getoption("--hardware-test")


@pytest.fixture
def config():
    config = load_config(ignore_local=True, simulator=['all'])
    config['db']['name'] = 'panoptes_testing'
    return config


@pytest.fixture
def db():
    return PanMongo(db='panoptes_testing')


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))
