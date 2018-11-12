import os
import pytest

from astropy import units as u
from pocs.utils import current_time
from pocs.camera import create_cameras_from_config
from pocs.observatory import Observatory
from pocs.core import POCS


@pytest.fixture(scope='function')
def cameras(config):
    """Get the default cameras from the config."""
    return create_cameras_from_config(config)


@pytest.fixture(scope='function')
def observatory(config, db_type, cameras):
    observatory = Observatory(
        config=config,
        cameras=cameras,
        simulator=['camera', 'mount', 'weather', 'night'],
        ignore_local_config=True,
        db_type=db_type
    )
    return observatory


@pytest.fixture(scope='function')
def pocs(config, observatory):
    os.environ['POCSTIME'] = '2016-08-13 13:00:00'

    pocs = POCS(observatory,
                run_once=False,
                config=config,
                ignore_local_config=True)

    yield pocs

    pocs.power_down()


def test_sleeping(pocs):
    os.environ['POCSTIME'] = '2016-09-09 06:00:00'

    # Insert a dummy power record
    pocs.db.insert_current('power', {'main': True})
    assert pocs.has_ac_power() is True

    pocs.initialize()

    # Start in sleeping
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    pocs.next_state = 'parking'
    assert pocs.goto_next_state()
    assert pocs.state == 'parking'
    assert pocs.observatory.current_observation is None
    assert pocs.observatory.mount.is_parked
    assert pocs.next_state == 'parked'
    assert pocs.goto_next_state()
    assert pocs.state == 'parked'

    # Force to housekeeping
    pocs.next_state = 'housekeeping'

    assert pocs.goto_next_state()
    assert pocs.state == 'housekeeping'
    assert pocs.next_state == 'sleeping'

    # Now it is morning
    os.environ['POCSTIME'] = '2016-09-09 20:00:00'
    assert pocs.run_once is False
    assert pocs.observatory.is_dark(horizon='flat') is False
    pocs._safe_delay = 5

    t0 = current_time()
    next_sunset = pocs.observatory.scheduler.observer.sun_set_time(
        t0,
        which='next',
        horizon=pocs.config['location']['flat_horizon']
    )
    os.environ['POCSTIME'] = (next_sunset - 10 * u.second).isot
    assert pocs.goto_next_state()
    assert pocs.state == 'sleeping'

    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.next_state == 'calibrating'
