import os
import threading
import time

import pytest
import requests
from astropy import units as u
from panoptes.pocs import hardware
from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory
from panoptes.utils.config.client import set_config
from panoptes.utils.serializers import to_json, to_yaml
from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.dome import create_dome_simulator
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.utils.location import create_location_from_config


def reset_conf(config_host, config_port):
    url = f'http://{config_host}:{config_port}/reset-config'
    response = requests.post(url,
                             data=to_json({'reset': True}),
                             headers={'Content-Type': 'application/json'}
                             )
    assert response.ok


@pytest.fixture(scope='function')
def cameras():
    return create_cameras_from_config()


@pytest.fixture(scope='function')
def mount():
    return create_mount_simulator()


@pytest.fixture(scope='function')
def pocstime_night():
    return "2020-01-01 08:00:00"


@pytest.fixture(scope='function')
def pocstime_day():
    return "2020-01-01 22:00:00"


@pytest.fixture(scope='function')
def site_details():
    return create_location_from_config()


@pytest.fixture(scope='function')
def scheduler(site_details):
    return create_scheduler_from_config(observer=site_details['observer'])


@pytest.fixture(scope='function')
def observatory(cameras, mount, site_details, scheduler):
    """Return a valid Observatory instance with a specific config."""

    obs = Observatory(scheduler=scheduler, simulator=['power', 'weather'])
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    obs.set_mount(mount)

    return obs


@pytest.fixture(scope='function')
def dome():
    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    })

    return create_dome_simulator()


@pytest.fixture(scope='function')
def pocs(observatory, config_host, config_port):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'

    pocs = POCS(observatory, run_once=True, simulators=['power'])
    yield pocs
    pocs.power_down()
    reset_conf(config_host, config_port)


@pytest.fixture(scope='function')
def pocs_with_dome(pocs, dome):
    # Add dome to config
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'
    pocs.observatory.set_dome(dome)
    yield pocs
    pocs.power_down()


# An observation that is valid during the day
@pytest.fixture(scope='module')
def valid_observation():
    return {"field": {'name': 'TEST TARGET',
                      'position': '100.00 deg +00.887 deg'},
            "observation": {'priority': '100',
                            'exptime': 2,
                            'min_nexp': 2,
                            'exp_set_size': 2}}


# An observation that is valid at night
@pytest.fixture(scope='module')
def valid_observation_day():
    return {"field": {'name': 'TEST TARGET',
                      'position': '300.00 deg +70.887 deg'},
            "observation": {'priority': '100',
                            'exptime': 2,
                            'min_nexp': 2,
                            'exp_set_size': 2}}


def test_observatory_cannot_observe(pocs):
    scheduler = pocs.observatory.scheduler
    pocs.observatory.scheduler = None
    assert pocs.initialize() is False
    pocs.observatory.scheduler = scheduler
    assert pocs.initialize()
    assert pocs.is_initialized
    # Make sure we can do it twice.
    assert pocs.initialize()
    assert pocs.is_initialized


def test_simple_simulator(pocs, caplog):
    assert isinstance(pocs, POCS)
    pocs.set_config('simulator', 'all')

    assert pocs.is_initialized is not True

    # Not initialized returns false and gives warning.
    assert pocs.run() is False
    log_record = caplog.records[-1]
    assert log_record.message == 'POCS not initialized' and log_record.levelname == "WARNING"

    pocs.initialize()
    assert pocs.is_initialized

    pocs.state = 'parking'
    pocs.next_state = 'parking'

    assert pocs._lookup_trigger() == 'set_park'

    pocs.state = 'foo'

    assert pocs._lookup_trigger() == 'parking'

    assert pocs.is_safe()


def test_is_weather_and_dark_simulator(pocs, pocstime_night, pocstime_day):
    pocs.initialize()

    # Night simulator
    pocs.set_config('simulator', 'all')
    os.environ['POCSTIME'] = pocstime_night  # is dark
    assert pocs.is_dark() is True
    os.environ['POCSTIME'] = pocstime_day  # is day
    assert pocs.is_dark() is True

    # No night simulator
    pocs.set_config('simulator', hardware.get_all_names(without=['night']))
    os.environ['POCSTIME'] = pocstime_night  # is dark
    assert pocs.is_dark() is True
    os.environ['POCSTIME'] = pocstime_day  # is day
    assert pocs.is_dark() is False

    pocs.set_config('simulator', ['camera', 'mount', 'weather', 'night'])
    assert pocs.is_weather_safe() is True


def test_is_weather_safe_no_simulator(pocs):
    pocs.initialize()
    pocs.set_config('simulator', hardware.get_all_names(without=['weather']))

    # Set a specific time
    os.environ['POCSTIME'] = '2020-01-01 18:00:00'

    # Insert a dummy weather record
    pocs.db.insert_current('weather', {'safe': True})
    assert pocs.is_weather_safe() is True

    # Set a time 181 seconds later
    os.environ['POCSTIME'] = '2020-01-01 18:05:01'
    assert pocs.is_weather_safe() is False


def test_no_ac_power(pocs):
    # Simulator makes AC power safe
    assert pocs.has_ac_power() is True

    # Remove 'power' from simulator
    pocs.set_config('simulator', hardware.get_all_names(without=['power']))

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


def test_run_no_targets_and_exit(pocs):
    os.environ['POCSTIME'] = '2020-01-01 19:00:00'
    pocs.set_config('simulator', 'all')

    pocs.state = 'sleeping'

    pocs.initialize()
    pocs.observatory.scheduler.clear_available_observations()
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'


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
    pocs.logger.warning('Inserting safe weather reading')
    pocs.db.insert_current('weather', {'safe': True})

    assert pocs.is_safe() is True
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    pocs.logger.warning('Moving to ready')
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    pocs.logger.warning('Moving to scheduling')
    assert pocs.goto_next_state()
    assert pocs.observatory.current_observation is not None
    pocs.next_state = 'parking'
    pocs.logger.warning('Moving to parking')
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


def test_run_wait_until_safe(observatory, valid_observation_day, pocstime_day, pocstime_night):
    os.environ['POCSTIME'] = pocstime_day

    # Remove weather simulator, else it would always be safe.
    observatory.set_config('simulator', hardware.get_all_names(without=['night']))

    pocs = POCS(observatory)
    pocs.set_config('wait_delay', 5)  # Check safety every 5 seconds.

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation_day)

    assert pocs.connected is True
    assert pocs.is_initialized is False
    pocs.initialize()
    pocs.logger.info('Starting observatory run')

    # Not dark and unit is is connected but not set.
    assert not pocs.is_dark()
    assert pocs.is_initialized
    assert pocs.connected
    assert pocs.do_states
    assert pocs.next_state is None

    pocs.set_config('wait_delay', 1)

    def start_pocs():
        # Start running, BLOCKING.
        pocs.logger.info('start_pocs ENTER')
        pocs.run(run_once=True, exit_when_done=True)

        # After done running.
        assert pocs.is_weather_safe() is True
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    assert pocs.is_safe(park_if_not_safe=False) is False

    # Wait to pretend we're waiting for horizon
    time.sleep(5)
    os.environ['POCSTIME'] = pocstime_night
    assert pocs.is_dark()

    pocs.logger.warning('Waiting to get to slewing state...')
    while pocs.next_state != 'slewing':
        time.sleep(1)

    pocs.logger.warning('Stopping states via pocs.DO_STATES')
    observatory.set_config('pocs.DO_STATES', False)

    observatory.logger.warning('Waiting on pocs_thread')
    pocs_thread.join(timeout=300)

    assert pocs_thread.is_alive() is False


def test_unsafe_park(observatory, valid_observation, pocstime_night):
    os.environ['POCSTIME'] = pocstime_night

    # Remove weather simulator, else it would always be safe.
    observatory.set_config('simulator', hardware.get_all_names(without=['night', 'weather']))

    pocs = POCS(observatory)
    pocs.set_config('wait_delay', 5)  # Check safety every 5 seconds.

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation)
    observatory.logger.warning('Inserting safe weather reading')
    observatory.db.insert_current('weather', {'safe': True})

    assert pocs.connected is True
    assert pocs.is_initialized is False
    pocs.initialize()
    pocs.logger.info('Starting observatory run')

    # Weather is bad and unit is is connected but not set.
    assert pocs.is_safe()
    assert pocs.is_initialized
    assert pocs.connected
    assert pocs.do_states
    assert pocs.next_state is None

    pocs.set_config('wait_delay', 1)

    def start_pocs():
        # Start running, BLOCKING.
        pocs.logger.info('start_pocs ENTER')
        pocs.run(run_once=True, exit_when_done=True)

        # After done running.
        assert pocs.is_weather_safe() is False
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    # Insert bad weather report while slewing
    pocs.logger.info('Waiting to get to slewing state...')
    while pocs.state != "slewing":
        pass
    pocs.logger.info("Inserting bad weather record.")
    observatory.db.insert_current('weather', {'safe': False})

    # No longer safe, so should transition to parking
    pocs.logger.info('Waiting to get to parked state...')
    while True:
        if pocs.state in ['parking', 'parked']:
            break
        assert pocs.state in ["slewing", "parking", "parked"]  # Should be one of these states
        time.sleep(0.5)

    pocs.logger.warning('Stopping states via pocs.DO_STATES')
    observatory.set_config('pocs.DO_STATES', False)

    observatory.logger.warning('Waiting on pocs_thread')
    pocs_thread.join(timeout=300)

    assert pocs_thread.is_alive() is False


def test_run_power_down_interrupt(observatory,
                                  valid_observation,
                                  pocstime_night
                                  ):
    os.environ['POCSTIME'] = pocstime_night

    observatory.logger.info('start_pocs ENTER')
    # Remove weather simulator, else it would always be safe.
    observatory.set_config('simulator', 'all')

    pocs = POCS(observatory)
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

    while pocs.next_state != 'slewing':
        pocs.logger.debug(
            f'Waiting to get to slewing state. Currently next_state={pocs.next_state}')
        time.sleep(1)

    pocs.logger.warning('Stopping states via pocs.DO_STATES')
    observatory.set_config('pocs.DO_STATES', False)

    observatory.logger.debug('Waiting on pocs_thread')
    pocs_thread.join(timeout=300)

    assert pocs_thread.is_alive() is False


def test_custom_state_file(observatory, temp_file, config_host, config_port):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    with open(temp_file, 'w') as f:
        f.write(to_yaml(state_table))

    file_path = os.path.abspath(temp_file)

    pocs = POCS(observatory, state_machine_file=file_path, run_once=True, simulators=['power'])
    pocs.initialize()
    pocs.power_down()
    reset_conf(config_host, config_port)


def test_free_space(pocs, caplog):
    assert pocs.has_free_space()

    assert pocs.has_free_space(required_space=999 * u.terabyte) is False
    assert 'No disk space' in caplog.records[-1].message
    assert caplog.records[-1].levelname == 'ERROR'


def test_run_complete(pocs, valid_observation):
    os.environ['POCSTIME'] = '2020-01-01 08:00:00'
    pocs.set_config('simulator', 'all')

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation(valid_observation)

    pocs.initialize()
    assert pocs.is_initialized is True

    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'
    pocs.power_down()
