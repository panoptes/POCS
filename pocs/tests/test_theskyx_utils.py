import os
import pytest
import requests

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
    if 'theskyx' in request.config.getoption('--with-hardware'):
        Mocket.disable()

    theskyx = TheSkyX(connect=False)

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


def test_no_connect_write(skyx):
    with pytest.raises(error.BadConnection):
        skyx.write('/* Java Script */')


def test_no_connect_read(skyx):
    with pytest.raises(error.BadConnection):
        skyx.read()


def test_write_bad_key(skyx):
    skyx.connect()
    skyx.write('FOOBAR')
    with pytest.raises(error.TheSkyXKeyError):
        skyx.read()


def test_write_no_command(skyx):
    skyx.connect()
    skyx.write('/* Java Script */')
    assert skyx.read() == 'undefined'


def test_get_build(skyx):
    js = '''
/* Java Script */
var Out;
Out=Application.version
'''
    skyx.connect()
    skyx.write(js)
    assert skyx.read().startswith('10.5')


def test_error(skyx):
    skyx.connect()
    skyx.write('''
/* Java Script */
sky6RASCOMTele.FindHome()
''')
    with pytest.raises(error.TheSkyXError):
        skyx.read()
