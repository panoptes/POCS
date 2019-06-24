import os
import pytest
import yaml

from pocs.core import POCS
from pocs.observatory import Observatory
from panoptes.utils import error


@pytest.fixture
def observatory(config_port):
    observatory = Observatory(simulator=['all'], config_port=config_port)

    yield observatory


def test_bad_state_machine_file():
    with pytest.raises(error.InvalidConfig):
        POCS.load_state_table(state_table_name='foo')


def test_load_bad_state(observatory, config_port):
    pocs = POCS(observatory, config_port=config_port)

    with pytest.raises(error.InvalidConfig):
        pocs._load_state('foo')


def test_state_machine_absolute(temp_file):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    with open(temp_file, 'w') as f:
        f.write(yaml.dump(state_table))

    file_path = os.path.abspath(temp_file)
    assert POCS.load_state_table(state_table_name=file_path)
