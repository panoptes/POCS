# pytest will load this file, adding the fixtures in it, if some of the tests
# in the same directory are selected, or if the current working directory when
# running pytest is the directory containing this file.
# Note that there are other fixtures defined in the conftest.py in the root
# of this project.

import copy
import os
import pytest

import pocs.base
from pocs.utils.config import load_config
from pocs.utils.logger import get_root_logger

# Global variable with the default config; we read it once, copy it each time it is needed.
_one_time_config = None


@pytest.fixture(scope='module')
def images_dir(tmpdir_factory):
    directory = tmpdir_factory.mktemp('images')
    return str(directory)


@pytest.fixture(scope='function')
def config(images_dir, messaging_ports):
    pocs.base.reset_global_config()

    global _one_time_config
    if not _one_time_config:
        _one_time_config = load_config(ignore_local=True, simulator=['all'])
        # Set several fields to fixed values.
        _one_time_config['db']['name'] = 'panoptes_testing'
        _one_time_config['name'] = 'PAN000'  # Make sure always testing with PAN000
        _one_time_config['scheduler']['fields_file'] = 'simulator.yaml'

    # Make a copy before we modify based on test fixtures.
    result = copy.deepcopy(_one_time_config)

    # We allow for each test to have its own images directory, and thus
    # to not conflict with each other.
    result['directories']['images'] = images_dir

    # For now (October 2018), POCS assumes that the pub and sub ports are
    # sequential. Make sure that is what the test fixtures have in them.
    # TODO(jamessynge): Remove this once pocs.yaml (or messaging.yaml?) explicitly
    # lists the ports to be used.
    assert messaging_ports['cmd_ports'][0] == (messaging_ports['cmd_ports'][1] - 1)
    assert messaging_ports['msg_ports'][0] == (messaging_ports['msg_ports'][1] - 1)

    # We don't want to use the same production messaging ports, just in case
    # these tests are running on a working scope.
    result['messaging']['cmd_port'] = messaging_ports['cmd_ports'][0]
    result['messaging']['msg_port'] = messaging_ports['msg_ports'][0]

    get_root_logger().debug('config fixture: {!r}', result)
    return result


@pytest.fixture
def config_with_simulated_dome(config):
    config.update({
        'dome': {
            'brand': 'Simulacrum',
            'driver': 'simulator',
        },
    })
    return config
