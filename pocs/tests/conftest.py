# pytest will load this file, adding the fixtures in it, if some of the tests
# in the same directory are selected, or if the current working directory when
# running pytest is the directory containing this file.

import copy
import os
import pytest

import pocs.base
from pocs.utils.config import load_config
from pocs.utils.database import PanDB
from pocs.utils.logger import get_root_logger

# Global variable with the default config; we read it once, copy it each time it is needed.
_one_time_config = None


@pytest.fixture(scope='function')
def config():
    pocs.base.reset_global_config()

    global _one_time_config
    if not _one_time_config:
        _one_time_config = load_config(ignore_local=True, simulator=['all'])
        _one_time_config['db']['name'] = 'panoptes_testing'

    return copy.deepcopy(_one_time_config)


@pytest.fixture
def config_with_simulated_dome(config):
    config.update({
        'dome': {
            'brand': 'Simulacrum',
            'driver': 'simulator',
        },
    })
    return config


_can_connect_to_mongo = None


def can_connect_to_mongo():
    global _can_connect_to_mongo
    if _can_connect_to_mongo is None:
        logger = get_root_logger()
        try:
            PanDB(
                db_type='mongo',
                db_name='panoptes_testing',
                logger=logger,
                connect=True
            )
            _can_connect_to_mongo = True
        except Exception:
            _can_connect_to_mongo = False
        logger.info('can_connect_to_mongo = {}', _can_connect_to_mongo)
    return _can_connect_to_mongo


@pytest.fixture(scope='function', params=['mongo', 'file'])
def db_type(request):
    # If testing mongo, make sure we can connect, otherwise skip.
    if request.param == 'mongo' and not can_connect_to_mongo():
        pytest.skip("Can't connect to {} DB, skipping".format(request.param))
    return request.param


@pytest.fixture(scope='function')
def db(db_type):
    return PanDB(
        db_type=db_type,
        db_name='panoptes_testing',
        logger=get_root_logger(),
        connect=True
    )


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))


class FakeLogger:
    def __init__(self):
        self.messages = []
        pass

    def _add(self, name, *args):
        msg = [name]
        assert len(args) == 1
        assert isinstance(args[0], tuple)
        msg.append(args[0])
        self.messages.append(msg)

    def debug(self, *args):
        self._add('debug', args)

    def info(self, *args):
        self._add('info', args)

    def warning(self, *args):
        self._add('warning', args)

    def error(self, *args):
        self._add('error', args)

    def critical(self, *args):
        self._add('critical', args)


@pytest.fixture(scope='function')
def fake_logger():
    return FakeLogger()
