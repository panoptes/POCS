import pytest

from panoptes.pocs.base import PanBase

from panoptes.utils.config.client import set_config
from panoptes.utils.database import PanDB


# def test_mount_in_config(config_port):
#     set_config('mount', {}, port=config_port)
#     with pytest.raises(SystemExit):
#         PanBase(config_port=config_port)


# def test_directories_in_config(config_port):
#     set_config('directories', {}, port=config_port)
#     with pytest.raises(SystemExit):
#         PanBase(config_port=config_port)


# def test_state_machine_in_config(config_port):
#     set_config('state_machine', {}, port=config_port)
#     with pytest.raises(SystemExit):
#         PanBase(config_port=config_port)


def test_with_logger(config_port):
    PanBase(config_port=config_port)


def test_with_db(config_port):
    base = PanBase(config_port=config_port, db=PanDB(db_type='memory', db_name='tester'))
    assert isinstance(base, PanBase)
