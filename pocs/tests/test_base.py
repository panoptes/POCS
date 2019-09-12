import pytest

from pocs.base import PanBase


def test_mount_in_config(config):
    del config['mount']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)


def test_directories_in_config(config):
    del config['directories']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)


def test_state_machine_in_config(config):
    del config['state_machine']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)
