import pytest

from pocs.base import PanBase
from panoptes.utils.config.client import set_config


def test_mount_in_config(config_port):
    set_config('mount', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)


def test_directories_in_config(config_port):
    set_config('directories', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)


def test_state_machine_in_config(config_port):
    set_config('state_machine', {}, port=config_port)
    with pytest.raises(SystemExit):
        PanBase(config_port=config_port)
