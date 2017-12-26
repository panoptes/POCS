import pytest

from pocs import PanBase


@pytest.fixture(params=[False, True], ids=['config_without_dome', 'config_with_dome'])
def config_to_check(request, config, config_with_simulated_dome):
    if request.param:
        return config_with_simulated_dome
    else:
        return config


def test_check_config1(config_to_check):
    del config_to_check['mount']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config_to_check)


def test_check_config2(config_to_check):
    del config_to_check['directories']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config_to_check)


def test_check_config3(config_to_check):
    del config_to_check['state_machine']
    base = PanBase()
    with pytest.raises(SystemExit):
        base._check_config(config_to_check)
