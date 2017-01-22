import pytest
from pocs_alerter.comet.parse_vo import ParseVO

from voeventparse.tests.resources.datapaths import swift_bat_grb_pos_v2 as test_vo

@pytest.fixture
def test_vo():
    return test_vo

@pytest.fixture
def channel():
    return 'ivo://nasa.gsfc.tan/gcn'


def test_valid_target_when_error_less_than_one_deg():

    alerter = ParseVO(test=True)
    v = alerter.read_in_vo()

    parsed, attribs = alerter.is_parsed_vo(v)
    assert parsed is True

    alerter.append_cands(attribs)
    assert len(alerter.checked_targets) > 0


def test_reading_vo(test_vo):

    alerter = ParseVO(test=True)

    v = alerter.read_in_vo()
    assert v is not None

    #alerter.test = False

    #with pytest.raises(FileNotFoundError):
    #    v = alerter.read_in_vo()


def test_reading_bad_vo():
    alerter = ParseVO()

    v = alerter.read_in_vo('not_a_real_file.lxml')
    assert v is None


def test_trusted_good_channel(channel):

    alerter = ParseVO()
    trusted = alerter.is_trusted(channel, 'author')
    assert trusted is True

def test_trusted_checker_breaks_author():

    alerter = ParseVO()
    trusted = alerter.is_trusted('bad channel', 'bad author')
    assert trusted is False


def test_trusted_checker_breaks_channel():

    alerter = ParseVO()
    trusted = alerter.is_trusted('bad channel', 'bad author')
    assert trusted is False

