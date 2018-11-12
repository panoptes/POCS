import os
import pytest

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
                run_once=True,
                config=config,
                ignore_local_config=True)

    yield pocs

    pocs.power_down()


def test_calibrating_no_flats(pocs):
    os.environ['POCSTIME'] = '2016-09-09 06:00:00'

    pocs.config['flat_field']['take_evening_flats'] = False
    pocs.initialize()

    # Start in sleeping
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.state == 'calibrating'
    assert pocs.goto_next_state()
    assert pocs.state == 'scheduling'


def test_calibrating(pocs):
    os.environ['POCSTIME'] = '2016-09-09 06:00:00'

    pocs.config['flat_field']['take_evening_flats'] = True
    pocs.initialize()

    # Start in sleeping
    assert pocs.state == 'sleeping'
    pocs.next_state = 'ready'
    assert pocs.initialize()
    assert pocs.goto_next_state()
    assert pocs.state == 'ready'
    assert pocs.goto_next_state()
    assert pocs.state == 'calibrating'
    assert pocs.goto_next_state()
    assert pocs.state == 'scheduling'
