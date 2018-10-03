# pytest will load this file, adding the fixtures in it, if some of the tests
# in the same directory are selected, or if the current working directory when
# running pytest is the directory containing this file.
# Note that there are other fixtures defined in the conftest.py in the root
# of this project.

import copy
import os
import signal
import subprocess
import time
from warnings import warn
import pytest
import Pyro4

import pocs.base
from pocs.utils.config import load_config

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


@pytest.fixture
def data_dir():
    return '{}/pocs/tests/data'.format(os.getenv('POCS'))


def end_process(proc):
    expected_return = 0
    if proc.poll() is None:
        # I'm not dead!
        expected_return = -signal.SIGINT
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired as err:
            warn("Timeout waiting for {} to exit!".format(proc.pid))
            if proc.poll() is None:
                # I'm getting better!
                warn("Sending SIGTERM to {}...".format(proc.pid))
                expected_return = -signal.SIGTERM
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired as err:
                    warn("Timeout waiting for {} to terminate!".format(proc.pid))
                    if proc.poll() is None:
                        # I feel fine!
                        warn("Sending SIGKILL to {}...".format(proc.pid))
                        expected_return = -signal.SIGKILL
                        proc.kill()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired as err:
                            warn("Timeout waiting for {} to die! Giving up".format(proc.pid))
                            raise err
    else:
        warn("Process {} already exited!".format(proc.pid))

    if proc.returncode != expected_return:
        warn("Expected return code {} from {}, got {}!".format(expected_return,
                                                               proc.pid,
                                                               proc.returncode))
    return proc.returncode


@pytest.fixture(scope='session')
def name_server(request):
    ns_cmds = [os.path.expandvars('$POCS/scripts/pyro_name_server.py'),
               '--host', 'localhost']
    ns_proc = subprocess.Popen(ns_cmds)
    request.addfinalizer(lambda: end_process(ns_proc))
    # Give name server time to start up
    waited = 0
    while waited <= 10:
        try:
            Pyro4.locateNS(host='localhost')
        except Pyro4.errors.NamingError:
            time.sleep(1)
            waited += 1
        else:
            return ns_proc

    raise TimeoutError("Timeout waiting for name server to start")


@pytest.fixture(scope='session')
def camera_server(name_server, request):
    cs_cmds = [os.path.expandvars('$POCS/scripts/pyro_camera_server.py'),
               '--ignore_local']
    cs_proc = subprocess.Popen(cs_cmds)
    request.addfinalizer(lambda: end_process(cs_proc))
    # Give camera server time to start up
    time.sleep(3)
    return cs_proc
