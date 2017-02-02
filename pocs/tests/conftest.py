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
    parser.addoption("--camera", action="store_true", default=False, help="If a real camera attached")
    parser.addoption("--mount", action="store_true", default=False, help="If a real mount attached")
    parser.addoption("--weather", action="store_true", default=False, help="If a real weather station attached")
    parser.addoption("--solve", action="store_true", default=False, help="If tests that require solving should be run")


@pytest.fixture
def config():
    config = load_config(ignore_local=True)
    config['db']['name'] = 'panoptes_testing'
    return config


@pytest.fixture
def db():
    return PanMongo(db='panoptes_testing')


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))
