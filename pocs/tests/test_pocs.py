import os
import time
import threading
import pytest

from astropy import units as u

from pocs import hardware

from pocs.core import POCS
from pocs.dome import create_dome_from_config
from pocs.observatory import Observatory
from panoptes.utils import CountdownTimer
from panoptes.utils import current_time
from panoptes.utils import error
from panoptes.utils.messaging import PanMessaging
from panoptes.utils.config.client import set_config

from pocs.camera import create_simulator_cameras
from pocs.scheduler import create_scheduler_from_config
from pocs.utils.location import create_location_from_config


def wait_for_running(sub, max_duration=90):
    """Given a message subscriber, wait for a RUNNING message."""
    timeout = CountdownTimer(max_duration)
    while not timeout.expired():
        topic, msg_obj = sub.receive_message()
        if msg_obj and 'RUNNING' == msg_obj.get('message'):
            return True
    return False


def wait_for_state(sub, state, max_duration=90):
    """Given a message subscriber, wait for the specified state."""
    timeout = CountdownTimer(max_duration)
    while not timeout.expired():
        topic, msg_obj = sub.receive_message()
        if topic == 'STATUS' and msg_obj and msg_obj.get('state') == state:
            return True
    return False


@pytest.fixture(scope='function')
def cameras(dynamic_config_server, config_port):
    return create_simulator_cameras(config_port=config_port)


@pytest.fixture(scope='function')
def site_details(dynamic_config_server, config_port):
    return create_location_from_config(config_port=config_port)


def dome(dynamic_config_server, config_port, scope='function'):
    return create_dome_from_config(config_port=config_port)


@pytest.fixture(scope='function')
def scheduler(dynamic_config_server, config_port, site_details):
    return create_scheduler_from_config(config_port=config_port,
                                        observer=site_details['observer'])


@pytest.fixture
def observatory(dynamic_config_server, config_port, cameras, scheduler, site_details):
    """Return a valid Observatory instance with a specific config."""
    obs = Observatory(scheduler=scheduler,
                      config_port=config_port,
                      )
    for cam_name, cam in cameras.items():
        obs.add_camera(cam_name, cam)

    return obs


@pytest.fixture(scope='function')
def pocs(dynamic_config_server, config_port, observatory):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    pocs = POCS(observatory, run_once=True, config_port=config_port)

    yield pocs

    pocs.power_down()


@pytest.fixture(scope='function')
def pocs_with_dome(dynamic_config_server, config_port, db_type, scheduler):
    # Add dome to config
    set_config('dome', {
        'brand': 'Simulacrum',
        'driver': 'simulator',
    }, port=config_port)
    set_config('simulator', hardware.get_all_names(without=['dome']), port=config_port)

    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    dome = create_dome_from_config(config_port)
    observatory = Observatory(scheduler=scheduler, dome=dome, config_port=config_port)
    pocs = POCS(observatory, config_port=config_port)
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

    assert pocs.has_free_space() is True

    # Test something ridiculous
    assert pocs.has_free_space(required_space=1e9 * u.gigabyte) is False

    assert pocs.is_safe() is True


def test_is_weather_and_dark_simulator(dynamic_config_server, config_port, pocs):
    pocs.initialize()
    set_config('simulator', ['camera', 'mount', 'weather', 'night'], port=config_port)
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is True

    set_config('simulator', ['camera', 'mount', 'weather'], port=config_port)
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    assert pocs.is_dark() is True

    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    assert pocs.is_dark() is False

    set_config('simulator', ['camera', 'mount', 'weather', 'night'], port=config_port)
    assert pocs.is_weather_safe() is True


def test_wait_for_events_timeout(pocs):
    del os.environ['POCSTIME']
    test_event = threading.Event()

    # Test timeout
    with pytest.raises(error.Timeout):
        pocs.wait_for_events(test_event, 1)

    # Test timeout
    with pytest.raises(error.Timeout):
        pocs.wait_for_events(test_event, 5 * u.second, sleep_delay=1)

    test_event = threading.Event()

    def set_event():
        test_event.set()

    # Mark as set in 1 second
    t = threading.Timer(1.0, set_event)
    t.start()

    # Wait for 10 seconds (should trip in 1 second)
    pocs.wait_for_events(test_event, 10)
    assert test_event.is_set()

    test_event = threading.Event()

    def set_event():
        while test_event.is_set() is False:
            time.sleep(1)

    def interrupt():
        pocs._interrupted = True

    # Wait for 60 seconds (interrupts below)
    t = threading.Timer(60.0, set_event)
    t.start()

    # Interrupt - Time to test status and messaging
    t2 = threading.Timer(3.0, interrupt)

    # Wait for 60 seconds (should interrupt from above)
    start_time = current_time()
    t2.start()
    pocs.wait_for_events(test_event, 60, sleep_delay=1., status_interval=1, msg_interval=1)
    end_time = current_time()
    assert test_event.is_set() is False
    assert (end_time - start_time).sec < 10
    test_event.set()
    t.cancel()
    t2.cancel()


def test_is_weather_safe_no_simulator(dynamic_config_server, config_port, pocs):
    pocs.initialize()
    set_config('simulator', ['camera', 'mount', 'night'], port=config_port)

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


def test_run_wait_until_safe(dynamic_config_server,
                             config_port,
                             observatory,
                             cmd_publisher,
                             msg_subscriber,
                             messaging_ports):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'

    set_config('messaging.cmd_port', messaging_ports['cmd_ports'][0], port=config_port)
    set_config('messaging.msg_port', messaging_ports['msg_ports'][0], port=config_port)

    # Make sure DB is clear for current weather
    observatory.db.clear_current('weather')

    def start_pocs():
        observatory.logger.info('start_pocs ENTER')
        # Remove weather simulator, else it would always be safe.
        set_config('simulator', hardware.get_all_names(without=['weather']), port=config_port)

        pocs = POCS(observatory, messaging=True, safe_delay=5, config_port=config_port)
        pocs.logger.critical(f'Created pocs')

        pocs.observatory.scheduler.clear_available_observations()
        pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                    'position': '20h06m15.4536s +44d27m24.75s',
                                                    'priority': '100',
                                                    'exptime': 2,
                                                    'min_nexp': 2,
                                                    'exp_set_size': 2,
                                                    })

        pocs.initialize()
        pocs.logger.info('Starting observatory run')
        assert pocs.is_weather_safe() is False
        pocs.send_message('RUNNING')
        pocs.run(run_once=True, exit_when_done=True)
        assert pocs.is_weather_safe() is True
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    try:
        # Wait for the RUNNING message,
        assert wait_for_running(msg_subscriber)

        time.sleep(2)
        # Insert a dummy weather record to break wait
        observatory.db.insert_current('weather', {'safe': True})

        assert wait_for_state(msg_subscriber, 'scheduling')
    finally:
        cmd_publisher.send_message('POCS-CMD', 'shutdown')
        pocs_thread.join(timeout=30)

    assert pocs_thread.is_alive() is False


def test_unsafe_park(dynamic_config_server, config_port, pocs):
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


def test_run_no_targets_and_exit(dynamic_config_server, config_port, pocs):
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'
    set_config('simulator', hardware.get_all_names(), port=config_port)

    pocs.state = 'sleeping'

    pocs.initialize()
    pocs.observatory.scheduler.clear_available_observations()
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'


def test_run_complete(dynamic_config_server, config_port, pocs):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'
    set_config('simulator', hardware.get_all_names(), port=config_port)

    pocs.state = 'sleeping'
    pocs._do_states = True

    pocs.observatory.scheduler.clear_available_observations()
    pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                        'position': '20h06m15.4536s +44d27m24.75s',
                                                        'priority': '100',
                                                        'exptime': 2,
                                                        'min_nexp': 2,
                                                        'exp_set_size': 2,
                                                })

    pocs.initialize()
    assert pocs.is_initialized is True

    pocs.run(exit_when_done=True, run_once=True)
    assert pocs.state == 'sleeping'
    pocs.power_down()


def test_run_power_down_interrupt(dynamic_config_server,
                                  config_port,
                                  observatory,
                                  cmd_publisher,
                                  msg_subscriber,
                                  messaging_ports):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'

    set_config('messaging.cmd_port', messaging_ports['cmd_ports'][0], port=config_port)
    set_config('messaging.msg_port', messaging_ports['msg_ports'][0], port=config_port)

    def start_pocs():
        observatory.logger.info('start_pocs ENTER')
        pocs = POCS(observatory, messaging=True, config_port=config_port)
        pocs.initialize()
        pocs.observatory.scheduler.clear_available_observations()
        pocs.observatory.scheduler.add_observation({'name': 'KIC 8462852',
                                                    'position': '20h06m15.4536s +44d27m24.75s',
                                                    'priority': '100',
                                                    'exptime': 2,
                                                    'min_nexp': 2,
                                                    'exp_set_size': 2,
                                                    })
        pocs.logger.info('Starting observatory run')
        pocs.run()
        pocs.power_down()
        observatory.logger.info('start_pocs EXIT')

    pocs_thread = threading.Thread(target=start_pocs, daemon=True)
    pocs_thread.start()

    try:
        assert wait_for_state(msg_subscriber, 'scheduling')
    finally:
        cmd_publisher.send_message('POCS-CMD', 'shutdown')
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
