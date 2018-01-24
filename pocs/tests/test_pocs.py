import os
import pytest
import time

from multiprocessing import Process

from astropy import units as u

from pocs import hardware
from pocs import POCS
from pocs.observatory import Observatory
from pocs.utils.messaging import PanMessaging


@pytest.fixture(scope='function')
def observatory(config, db):
    observatory = Observatory(
        config=config,
        simulator=['all'],
        ignore_local_config=True,
        db=db
    )
    return observatory


@pytest.fixture(scope='function')
def pocs(config, observatory, db):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    pocs = POCS(observatory,
                run_once=True,
                config=config,
                ignore_local_config=True, db='panoptes_testing')

    pocs.db = db
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
def pocs_with_dome(config_with_simulated_dome, db):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'
    simulator = hardware.get_all_names(without=['dome'])
    observatory = Observatory(config=config_with_simulated_dome,
                              simulator=simulator,
                              ignore_local_config=True)

    pocs = POCS(observatory,
                run_once=True,
                config=config_with_simulated_dome,
                ignore_local_config=True, db='panoptes_testing')
    pocs.db = db

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


def test_is_weather_safe_no_simulator(pocs, db):
    pocs.initialize()
    pocs.config['simulator'] = ['camera', 'mount', 'night']

    # Set a specific time
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'

    # Insert a dummy weather record
    db.insert_current('weather', {'safe': True})
    assert pocs.is_weather_safe() is True

    # Set a time 181 seconds later
    os.environ['POCSTIME'] = '2016-08-13 23:05:01'
    assert pocs.is_weather_safe() is False


def test_run_wait_until_safe(observatory, db):
    os.environ['POCSTIME'] = '2016-08-13 23:00:00'

    def start_pocs():
        observatory.config['simulator'] = ['camera', 'mount', 'night']

        pocs = POCS(observatory,
                    messaging=True, safe_delay=15)
        pocs.db = db
        pocs.initialize()
        pocs.logger.info('Starting observatory run')
        assert pocs.is_weather_safe() is False
        pocs.send_message('RUNNING')
        pocs.run(run_once=True, exit_when_done=True)
        assert pocs.is_weather_safe() is True
        pocs.power_down()

    pub = PanMessaging.create_publisher(6500)
    sub = PanMessaging.create_subscriber(6511)

    pocs_process = Process(target=start_pocs)
    pocs_process.start()

    # Wait for the running message
    while True:
        msg_type, msg_obj = sub.receive_message()
        if msg_obj is None:
            time.sleep(2)
            continue

        if msg_obj.get('message', '') == 'RUNNING':
            time.sleep(2)
            # Insert a dummy weather record to break wait
            db.insert_current('weather', {'safe': True})

        if msg_type == 'STATUS':
            current_state = msg_obj.get('state', {})
            if current_state == 'pointing':
                pub.send_message('POCS-CMD', 'shutdown')
                break

        time.sleep(0.5)

    pocs_process.join()
    assert pocs_process.is_alive() is False


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
    assert pocs.is_initialized is True
    pocs.run(exit_when_done=True)
    assert pocs.state == 'sleeping'


def test_run_complete(pocs):
    os.environ['POCSTIME'] = '2016-09-09 08:00:00'
    pocs.config['simulator'] = ['camera', 'mount', 'weather', 'night']
    pocs.state = 'sleeping'
    pocs._do_states = True

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


def test_run_interrupt_with_reschedule_of_target(observatory):
    def start_pocs():
        pocs = POCS(observatory, messaging=True)
        pocs.logger.info('Before initialize')
        pocs.initialize()
        pocs.logger.info('POCS initialized, back in test')
        pocs.observatory.scheduler.fields_list = [{'name': 'KIC 8462852',
                                                   'position': '20h06m15.4536s +44d27m24.75s',
                                                   'priority': '100',
                                                   'exp_time': 2,
                                                   'min_nexp': 1,
                                                   'exp_set_size': 1,
                                                   }]
        pocs.run(exit_when_done=True, run_once=True)
        pocs.logger.info('run finished, powering down')
        pocs.power_down()

    pub = PanMessaging.create_publisher(6500)
    sub = PanMessaging.create_subscriber(6511)

    pocs_process = Process(target=start_pocs)
    pocs_process.start()

    while True:
        msg_type, msg_obj = sub.receive_message()
        if msg_type == 'STATUS':
            current_state = msg_obj.get('state', {})
            if current_state == 'pointing':
                pub.send_message('POCS-CMD', 'shutdown')
                break

    pocs_process.join()
    assert pocs_process.is_alive() is False


def test_run_power_down_interrupt(observatory):
    def start_pocs():
        pocs = POCS(observatory, messaging=True)
        pocs.initialize()
        pocs.observatory.scheduler.fields_list = [{'name': 'KIC 8462852',
                                                   'position': '20h06m15.4536s +44d27m24.75s',
                                                   'priority': '100',
                                                   'exp_time': 2,
                                                   'min_nexp': 1,
                                                   'exp_set_size': 1,
                                                   }]
        pocs.logger.info('Starting observatory run')
        pocs.run()
        pocs.power_down()

    pocs_process = Process(target=start_pocs)
    pocs_process.start()

    pub = PanMessaging.create_publisher(6500)
    sub = PanMessaging.create_subscriber(6511)

    while True:
        msg_type, msg_obj = sub.receive_message()
        if msg_type == 'STATUS':
            current_state = msg_obj.get('state', {})
            if current_state == 'pointing':
                pub.send_message('POCS-CMD', 'shutdown')
                break

    pocs_process.join()
    assert pocs_process.is_alive() is False
