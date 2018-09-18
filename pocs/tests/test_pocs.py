import os
import pytest
import time
import threading

from astropy import units as u

from pocs import hardware
from pocs.core import POCS
from pocs.observatory import Observatory
from pocs.utils import Timeout
from pocs.utils.messaging import PanMessaging


def wait_for_running(sub, max_duration=90):
    """Given a message subscriber, wait for a RUNNING message."""
    timeout = Timeout(max_duration)
    while not timeout.expired():
        topic, msg_obj = sub.receive_message()
        if msg_obj and 'RUNNING' == msg_obj.get('message'):
            return True
    return False


def wait_for_state(sub, state, max_duration=90):
    """Given a message subscriber, wait for the specified state."""
    timeout = Timeout(max_duration)
    while not timeout.expired():
        topic, msg_obj = sub.receive_message()
        if topic == 'STATUS' and msg_obj and msg_obj.get('state') == state:
            return True
    return False


@pytest.fixture(scope='function')
def observatory(config, db_type):
    observatory = Observatory(
        config=config,
        simulator=['all'],
        ignore_local_config=True,
        db_type=db_type
    )
    return observatory


@pytest.fixture(scope='function')
def pocs(config, observatory):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    pocs = POCS(observatory,
                run_once=True,
                config=config,
                ignore_local_config=True)

    pocs.observatory.scheduler.fields_file = None
    pocs.observatory.scheduler.fields_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         'exp_time': 2,
         'min_nexp': 2,
         'exp_set_size': 2,
         },
    ]

    yield pocs

    pocs.power_down()


@pytest.fixture(scope='function')
def pocs_with_dome(config_with_simulated_dome, db_type):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    simulator = hardware.get_all_names(without=['dome'])
    observatory = Observatory(config=config_with_simulated_dome,
                              simulator=simulator,
                              ignore_local_config=True,
                              db_type=db_type
                              )

    pocs = POCS(observatory,
                run_once=True,
                config=config_with_simulated_dome,
                ignore_local_config=True)

    pocs.observatory.scheduler.fields_list = [
        {'name': 'Wasp 33',
         'position': '02h26m51.0582s +37d33m01.733s',
         'priority': '100',
         'exp_time': 2,
         'min_nexp': 2,
         'exp_set_size': 2,
         },
    ]

    yield pocs

    pocs.power_down()


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


def test_make_log_dir(pocs):
    log_dir = "{}/logs".format(os.getcwd())
    assert os.path.exists(log_dir) is False

    old_pandir = os.environ['PANDIR']
    os.environ['PANDIR'] = os.getcwd()
    POCS.check_environment()

    assert os.path.exists(log_dir) is True
    os.removedirs(log_dir)

    os.environ['PANDIR'] = old_pandir


def test_simple_simulator(pocs):
    assert isinstance(pocs, POCS)


def test_not_initialized(pocs):
    assert pocs.is_initialized is not True


def test_run_without_initialize(pocs):
    with pytest.raises(AssertionError):
        pocs.run()


def test_initialization(pocs):
    pocs.initialize()
    assert pocs.is_initialized


def test_default_lookup_trigger(pocs):
    pocs.state = 'parking'
    pocs.next_state = 'parking'

    assert pocs._lookup_trigger() == 'set_park'

    pocs.state = 'foo'

    assert pocs._lookup_trigger() == 'parking'


def test_free_space(pocs):
    assert pocs.has_free_space() is True

    # Test something ridiculous
    assert pocs.has_free_space(required_space=1e9 * u.gigabyte) is False

    assert pocs.is_safe() is True


def test_is_dark_simulator(pocs):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is True


def test_is_dark_no_simulator_01(pocs):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True


def test_is_dark_no_simulator_02(pocs):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is False


def test_is_weather_safe_simulator(pocs):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    assert pocs.is_weather_safe() is True


def test_is_weather_safe_no_simulator(pocs):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'night']

    # Set a specific time
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'

    # Insert a dummy weather record
    pocs.db.insert_current('weather', {'safe': True})
    assert pocs.is_weather_safe() is True

    # Set a time 181 seconds later
    os.environ['POCSTIME'] = '2016-08-13 23:05:01'
    assert pocs.is_weather_safe() is False


def wait_for_message(sub, type=None, attr=None, value=None):
    """Wait for a message of the specified type and contents."""
    assert (attr is None) == (value is None)
    while True:
        topic, msg_obj = sub.receive_message()
        if not msg_obj:
            continue
        if type and topic != type:
            continue
        if not attr or attr not in msg_obj:
            continue
        if value and msg_obj[attr] != value:
            continue
        return topic, msg_obj


def test_run_wait_until_evening(observatory):
    os.environ['POCSTIME'] = '2016-09-09 03:00:00'

    # Make sure DB is clear for current weather
    observatory.db.clear_current('weather')

    def start_pocs():
        observatory.logger.info('start_pocs ENTER')
        # Remove weather simulator, else it would always be safe.
        observatory.config['simulator'] = hardware.get_all_names(without=['night'])

        pocs = POCS(observatory,
                    messaging=True, safe_delay=5)

        pocs.observatory.scheduler.clear_available_observations()
        pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                    'position': '20h06m15.4536s +44d27m24.75s',
                                                    'priority': '100',
                                                    'exp_time': 2,
                                                    'min_nexp': 2,
                                                    'exp_set_size': 2,
                                                    })

        pocs.initialize()
        pocs.logger.info('Starting observatory run')
        assert pocs.observatory.is_dark(horizon='flat') is False
        pocs.send_message('RUNNING')
        pocs.run(run_once=True, exit_when_done=True)
        assert pocs.observatory.is_dark(horizon='flat') is True
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pub = PanMessaging.create_publisher(6500)
    sub = PanMessaging.create_subscriber(6511)

    pocs_thread = threading.Thread(target=start_pocs)
    pocs_thread.start()

    try:
        # Wait for the RUNNING message,
        assert wait_for_running(sub)

        time.sleep(2)
        # Insert a dummy weather record to break wait
        os.environ['POCSTIME'] = '2016-09-09 05:00:00'

        assert wait_for_state(sub, 'ready')
    finally:
        pub.send_message('POCS-CMD', 'shutdown')
        pocs_thread.join(timeout=30)

    assert pocs_thread.is_alive() is False


def test_unsafe_park(pocs):
    pocs.initialize()
    assert pocs.is_initialized is True
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.state == 'sleeping'
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.schedule()
    assert pocs.state == 'scheduling'

    # My time goes fast...
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    pocs.config['simulator'] = ['camera', 'mount', 'weather']
    assert pocs.is_safe() is False

    assert pocs.state == 'parking'
    pocs.set_park()
    pocs.clean_up()
    pocs.goto_sleep()
    assert pocs.state == 'sleeping'
    pocs.power_down()


def test_power_down_while_running(pocs):
    assert pocs.connected is True
    assert not pocs.observatory.has_dome
    pocs.initialize()
    pocs.get_ready()
    assert pocs.state == 'ready'
    pocs.power_down()

    assert pocs.state == 'parked'
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

    assert pocs.state == 'parked'
    assert pocs.connected is False
    assert not pocs.observatory.dome.is_connected


def test_run_no_targets_and_exit(pocs):
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']
    pocs.state = 'sleeping'

    pocs.initialize()
    pocs.observatory.scheduler.clear_available_observations()
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'


def test_run_complete(pocs):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']
    pocs.state = 'sleeping'
    pocs._do_states = True

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                        'position': '20h06m15.4536s +44d27m24.75s',
                                                        'priority': '100',
                                                        'exp_time': 2,
                                                        'min_nexp': 2,
                                                        'exp_set_size': 2,
                                                })

    pocs.initialize()
    assert pocs.is_initialized is True

    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'
    pocs.power_down()


def test_run_power_down_interrupt(observatory):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'

    def start_pocs():
        observatory.logger.info('start_pocs ENTER')
        pocs = POCS(observatory, messaging=True)
        pocs.initialize()
        pocs.observatory.scheduler.clear_available_observations()
        pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                    'position': '20h06m15.4536s +44d27m24.75s',
                                                    'priority': '100',
                                                    'exp_time': 2,
                                                    'min_nexp': 2,
                                                    'exp_set_size': 2,
                                                    })
        pocs.logger.info('Starting observatory run')
        pocs.run()
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs)
    pocs_thread.start()

    pub = PanMessaging.create_publisher(6500)
    sub = PanMessaging.create_subscriber(6511)

    try:
        assert wait_for_state(sub, 'scheduling')
    finally:
        pub.send_message('POCS-CMD', 'shutdown')
        pocs_thread.join(timeout=30)

    assert pocs_thread.is_alive() is False


def test_pocs_park_to_ready_with_observations(pocs):
    # We don't want to run_once here
    pocs._run_once = False

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
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    # Should be safe and still have valid observations so next state should
    # be ready
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    pocs.power_down()
    assert pocs.connected is False


def test_pocs_park_to_ready_without_observations(pocs):

    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

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

    # Since we don't have valid observations we will start sleeping for 30
    # minutes so send shutdown command first.
    pub = PanMessaging.create_publisher(6500)
    pub.send_message('POCS-CMD', 'shutdown')
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'
    pocs.power_down()

    assert pocs.connected is False
    assert pocs.is_safe() is False
