import pytest
from mocket import Mocket
from panoptes.pocs.utils.theskyx import TheSkyX
from panoptes.utils import error


@pytest.fixture(scope="function")
def skyx(data_dir, request):
    """Create TheSkyX class but don't connect.

    If running with a real connection TheSkyX then the Mocket will
    be disabled here.
    """

    # Use `--theskyx thesky` on cli to run without mock
    Mocket.enable('theskyx', data_dir)
    if request.config.getoption('--theskyx'):
        Mocket.disable()

    theskyx = TheSkyX(connect=False)

    yield theskyx
    Mocket.disable()


def test_default_connect(data_dir, request):
    """Test connection to TheSkyX

    If not running with a real connection then use Mocket
    """
    # Use `--theskyx thesky` on cli to run without mock
    if not request.config.getoption('--theskyx'):
        Mocket.enable('theskyx', data_dir)

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
