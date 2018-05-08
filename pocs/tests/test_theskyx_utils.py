import os
import pytest

from mocket import Mocket

from pocs.utils import error
from pocs.utils.theskyx import TheSkyX


@pytest.fixture(scope="function")
def skyx(request):
    """Create TheSkyX class but don't connect.t

    If running with a real connection TheSkyX then the Mokcet will
    be disabled here.
    """

    # Use `--with-hardware thesky` on cli to run without mock
    Mocket.enable('theskyx', '{}/pocs/tests/data'.format(os.getenv('POCS')))
    if 'theskyx' in pytest.config.getoption('--with-hardware'):
        Mocket.disable()

    theskyx = TheSkyX()

    yield theskyx


def test_default_connect():
    """Test connection to TheSkyX

    If not running with a real connection then use Mocket
    """
    # Use `--with-hardware thesky` on cli to run without mock
    if 'theskyx' not in pytest.config.getoption('--with-hardware'):
        Mocket.enable('theskyx', '{}/pocs/tests/data'.format(os.getenv('POCS')))

    skyx = TheSkyX()
    assert skyx.is_connected is True


def test_write_bad_template(skyx):
    with pytest.raises(AssertionError):
        skyx.query('FOOBAR')


def test_write_no_command(skyx):
    assert skyx._query('/* Java Script */') == 'undefined'


def test_get_build(skyx):
    js = '''
/* Java Script */
Out=Application.version
'''
    response = skyx._query(js)
    assert response.startswith('10.5')
