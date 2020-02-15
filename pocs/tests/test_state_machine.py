import os
import pytest

from pocs.core import POCS
from pocs.observatory import Observatory
from panoptes.utils import error
from panoptes.utils.serializers import to_yaml


@pytest.fixture
def observatory(dynamic_config_server, config_port):
    observatory = Observatory(simulator=['all'], config_port=config_port)

    yield observatory


def test_bad_state_machine_file():
    with pytest.raises(error.InvalidConfig):
        POCS.load_state_table(state_table_name='foo')


def test_load_bad_state(dynamic_config_server, config_port, observatory):
    pocs = POCS(observatory, config_port=config_port)

    with pytest.raises(error.InvalidConfig):
        pocs._load_state('foo')


def test_load_state_info(observatory):
    pocs = POCS(observatory)

    pocs._load_state('ready', state_info={'tags': ['at_twilight']})


def test_state_machine_absolute(temp_file):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    with open(temp_file, 'w') as f:
        f.write(to_yaml(state_table))

    file_path = os.path.abspath(temp_file)
    assert POCS.load_state_table(state_table_name=file_path)
