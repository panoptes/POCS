import pytest

from pocs import PanBase


def test_check_config1(config):
    del config['mount']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)


def test_check_config2(config):
    del config['directories']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)


def test_check_config3(config):
    del config['state_machine']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config)
