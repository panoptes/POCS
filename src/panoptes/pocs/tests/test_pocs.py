import os
import threading
import time

import pytest

from panoptes.pocs import hardware

from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory
from panoptes.utils import CountdownTimer
from panoptes.utils.config.client import set_config

from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.dome import create_dome_simulator
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.utils.location import create_location_from_config


@pytest.fixture(scope='function')
def cameras(dynamic_config_server, config_port):
    return create_cameras_from_config(config_port=config_port)


@pytest.fixture(scope='function')
def mount(dynamic_config_server, config_port):
    return create_mount_simulator()


@pytest.fixture(scope='function')
def site_details(dynamic_config_server, config_port):
    return create_location_from_config(config_port=config_port)


@pytest.fixture(scope='function')
def scheduler(dynamic_config_server, config_port, site_details):
    return create_scheduler_from_config(config_port=config_port, observer=site_details['observer'])


@pytest.fixture(scope='function')
def observatory(dynamic_config_server, config_port, cameras, mount, site_details, scheduler):
    """Return a valid Observatory instance with a specific config."""

    obs = Observatory(scheduler=scheduler, config_port=config_port)
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    obs.set_mount(mount)

    return obs


@pytest.fixture(scope='function')
def dome(config_port):
    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)

    return create_dome_simulator(config_port=config_port)


@pytest.fixture(scope='function')
def pocs(dynamic_config_server, config_port, observatory):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'

    pocs = POCS(observatory, run_once=True, config_port=config_port)
    yield pocs
    pocs.power_down()


@pytest.fixture(scope='function')
def pocs_with_dome(dynamic_config_server, config_port, pocs, dome):
    # Add dome to config
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'
    pocs.observatory.set_dome(dome)
    yield pocs
    pocs.power_down()


@pytest.fixture(scope='module')
def valid_observation():
    return {'name': 'HIP 36850',
            'position': '113.65 deg +31.887 deg',
            'priority': '100',
            'exptime': 2,
            'min_nexp': 2,
            'exp_set_size': 2,
            }


def test_bad_pandir_env(pocs):
    pandir = os.getenv('PANDIR')
    os.environ['PANDIR'] = '/foo/bar'
    with pytest.raises(SystemExit):
        POCS.check_environment()
    os.environ['PANDIR'] = pandir


def test_bad_pocs_env(pocs):
    pocs_dir = os.getenv('POCS')
    os.environ['POCS'] = '/foo/bar'
    with pytest.raises(SystemExit):
        POCS.check_environment()
    os.environ['POCS'] = pocs_dir


def test_make_log_dir(tmp_path, pocs):
    log_dir = tmp_path / 'logs'
    assert os.path.exists(log_dir) is False

    old_pandir = os.environ['PANDIR']
    os.environ['PANDIR'] = str(tmp_path.resolve())
    POCS.check_environment()

    assert os.path.exists(log_dir) is True
    os.removedirs(log_dir)

    os.environ['PANDIR'] = old_pandir


def test_simple_simulator(pocs):
    assert isinstance(pocs, POCS)

    assert pocs.is_initialized is not True

    with pytest.raises(AssertionError):
        pocs.run()

    pocs.initialize()
    assert pocs.is_initialized

    pocs.state = 'parking'
    pocs.next_state = 'parking'

    assert pocs._lookup_trigger() == 'set_park'

    pocs.state = 'foo'

    assert pocs._lookup_trigger() == 'parking'

    assert pocs.is_safe()


def test_is_weather_and_dark_simulator(dynamic_config_server, config_port, pocs):
    pocs.initialize()

    # Night simulator
    set_config('simulator', ['camera', 'mount', 'weather', 'night'], port=config_port)
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'  # is dark
    assert pocs.is_dark() is True
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'  # is day
    assert pocs.is_dark() is True

    # No night simulator
    set_config('simulator', ['camera', 'mount', 'weather'], port=config_port)
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'  # is dark
    assert pocs.is_dark() is True
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'  # is day
    assert pocs.is_dark() is False

    set_config('simulator', ['camera', 'mount', 'weather', 'night'], port=config_port)
    assert pocs.is_weather_safe() is True


def test_is_weather_safe_no_simulator(dynamic_config_server, config_port, pocs):
    pocs.initialize()
    set_config('simulator', ['camera', 'mount', 'night'], port=config_port)

    # Set a specific time
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'

    # Insert a dummy weather record
    pocs.db.insert_current('weather', {'safe': True})
    assert pocs.is_weather_safe() is True

    # Set a time 181 seconds later
    os.environ['POCSTIME'] = '2020-01-01 18:05:01'
    assert pocs.is_weather_safe() is False


def test_unsafe_park(dynamic_config_server, config_port, pocs):
    pocs.initialize()
    assert pocs.is_initialized is True
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'
    assert pocs.state == 'sleeping'
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.schedule()
    assert pocs.state == 'scheduling'

    # My time goes fast...
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'
    set_config('simulator', hardware.get_all_names(without=['night']), port=config_port)

    assert pocs.is_safe() is False

    assert pocs.state == 'parking'
    pocs.set_park()
    pocs.clean_up()
    pocs.goto_sleep()
    assert pocs.state == 'sleeping'
    pocs.power_down()


def test_no_ac_power(dynamic_config_server, config_port, pocs):
    # Simulator makes AC power safe
    assert pocs.has_ac_power() is True

    # Remove 'power' from simulator
    set_config('simulator', hardware.get_all_names(without=['power']), port=config_port)

    pocs.initialize()

    # With simulator removed the power should fail
    assert pocs.has_ac_power() is False

    for v in [True, 12.4, 0., False]:
        has_power = bool(v)

        # Add a fake power entry in data base
        pocs.db.insert_current('power', {'main': v})

        # Check for safe entry in database
        assert pocs.has_ac_power() == has_power
        assert pocs.is_safe() == has_power

        # Check for stale entry in database
        assert pocs.has_ac_power(stale=0.1) is False

        # But double check it still matches longer entry
        assert pocs.has_ac_power() == has_power

        # Remove entry and try again
        pocs.db.clear_current('power')
        assert pocs.has_ac_power() is False


def test_power_down_while_running(pocs):
    assert pocs.connected is True
    assert not pocs.observatory.has_dome
    pocs.initialize()
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.power_down()

    assert pocs.observatory.mount.is_parked
    assert pocs.connected is False


def test_power_down_dome_while_running(pocs_with_dome):
    pocs = pocs_with_dome
    assert pocs.connected is True
    assert pocs.observatory.has_dome
    assert not pocs.observatory.dome.is_connected
    pocs.initialize()
    assert pocs.observatory.dome.is_connected
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.power_down()

    assert pocs.observatory.mount.is_parked
    assert pocs.connected is False
    assert not pocs.observatory.dome.is_connected


def test_run_no_targets_and_exit(dynamic_config_server, config_port, pocs):
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'
    set_config('simulator', hardware.get_all_names(), port=config_port)

    pocs.state = 'sleeping'

    pocs.initialize()
    pocs.observatory.scheduler.clear_available_observations()
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'


def test_run_complete(dynamic_config_server, config_port, pocs, valid_observation):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'
    set_config('simulator', hardware.get_all_names(), port=config_port)

    pocs.state = 'sleeping'
    pocs._do_states = True

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation)

    pocs.initialize()
    assert pocs.is_initialized is True

    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'
    pocs.power_down()


def test_pocs_park_to_ready_with_observations(pocs):
    # We don't want to run_once here
    pocs.run_once = False

    assert pocs.is_safe() is True
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.state == 'scheduling'
    assert pocs.observatory.current_observation is not None

    # Manually set to parking
    pocs.next_state = 'parking'
    assert pocs.goto_next_state()
    assert pocs.state == 'parking'
    assert pocs.observatory.current_observation is None
    assert pocs.observatory.mount.is_parked
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    # Should be safe and still have valid observations so next state should be ready
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    pocs.power_down()
    assert pocs.connected is False


def test_pocs_park_to_ready_without_observations(pocs):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'

    assert pocs.is_safe() is True
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.observatory.current_observation is not None
    pocs.next_state = 'parking'
    assert pocs.goto_next_state()
    assert pocs.state == 'parking'
    assert pocs.observatory.current_observation is None
    assert pocs.observatory.mount.is_parked

    # No valid obs
    pocs.observatory.scheduler.clear_available_observations()

    pocs.interrupted = True
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    pocs.power_down()

    assert pocs.connected is False
    assert pocs.is_safe() is False


def test_run_wait_until_safe(observatory,
                             valid_observation,
                             config_port,
                             ):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'

    # Make sure DB is clear for current weather
    observatory.db.clear_current('weather')

    observatory.logger.info('start_pocs ENTER')
    # Remove weather simulator, else it would always be safe.
    set_config('simulator', hardware.get_all_names(without=['weather']), port=config_port)

    pocs = POCS(observatory, config_port=config_port)
    pocs.set_config('wait_delay', 5)  # Check safety every 5 seconds.

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation)

    pocs.initialize()
    pocs.logger.info('Starting observatory run')

    # Weather is bad and unit is is connected but not set.
    assert pocs.is_weather_safe() is False
    assert pocs.connected
    assert pocs.do_states
    assert pocs.is_initialized
    assert pocs.next_state is None

    pocs.set_config('wait_delay', 1)

    def start_pocs():
        # Start running, BLOCKING.
        pocs.logger.info(f'start_pocs ENTER')
        pocs.run(run_once=True, exit_when_done=True)

        # After done running.
        assert pocs.is_weather_safe() is True
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    # Wait until we are in the waiting state.
    while not pocs.next_state == 'ready':
        time.sleep(1)

    assert pocs.is_safe() is False

    # Wait to pretend we're waiting for weather
    time.sleep(2)

    # Insert a dummy weather record to break wait
    observatory.logger.warning(f'Inserting safe weather reading')
    observatory.db.insert_current('weather', {'safe': True})

    assert pocs.is_safe() is True

    while pocs.next_state != 'slewing':
        pocs.logger.warning(f'Waiting to get to scheduling state. Currently next_state={pocs.next_state}')
        time.sleep(1)

    pocs.logger.warning(f'Stopping states via pocs.DO_STATES')
    observatory.set_config('pocs.DO_STATES', False)

    observatory.logger.warning(f'Waiting on pocs_thread')
    pocs_thread.join(timeout=300)

    assert pocs_thread.is_alive() is False


def test_run_power_down_interrupt(config_port,
                                  observatory,
                                  valid_observation,
                                  ):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'

    observatory.logger.info('start_pocs ENTER')
    # Remove weather simulator, else it would always be safe.
    set_config('simulator', hardware.get_all_names(), port=config_port)

    pocs = POCS(observatory, config_port=config_port)
    pocs.set_config('wait_delay', 5)  # Check safety every 5 seconds.

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation)

    pocs.initialize()
    pocs.logger.info('Starting observatory run')

    # Weather is bad and unit is is connected but not set.
    assert pocs.connected
    assert pocs.do_states
    assert pocs.is_initialized
    assert pocs.next_state is None

    def start_pocs():
        observatory.logger.info('start_pocs ENTER')
        pocs.run(exit_when_done=True, run_once=True)
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    while pocs.next_state != 'scheduling':
        pocs.logger.debug(f'Waiting to get to scheduling state. Currently next_state={pocs.next_state}')
        time.sleep(1)

    pocs.logger.warning(f'Stopping states via pocs.DO_STATES')
    observatory.set_config('pocs.DO_STATES', False)

    observatory.logger.debug(f'Waiting on pocs_thread')
    pocs_thread.join(timeout=300)

    assert pocs_thread.is_alive() is False
