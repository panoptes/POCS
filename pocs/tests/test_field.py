import pytest

from astropy import units as u
from astropy.coordinates import Latitude, Longitude

from pocs.scheduler.field import Field


def test_create_field_no_params(config_port):
    with pytest.raises(TypeError):
        Field()


def test_create_field_bad_position(config_port):
    with pytest.raises(ValueError):
        Field('TestObservation', 'Bad Position', config_port=config_port)


def test_create_field_bad_name(config_port):
    with pytest.raises(ValueError):
        Field('', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)
    with pytest.raises(ValueError):
        Field(' - ', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)


def test_create_field_name(config_port):
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)
    assert field.name == 'Test Field - 32b'


def test_equinox_none(config_port):
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s', equinox=None, config_port=config_port)
    assert field.coord.equinox == 'J2000'


def test_create_field_Observation_name(config_port):
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s', config_port=config_port)
    assert field.field_name == 'TestField32B'


def test_create_field(config_port):
    names = ['oneWord', 'Two Words', '3 Whole - Words']
    right_ascensions = [
        ('20h00m43.7135s', Longitude('20h00m43.7135s', unit=u.degree)),
        ('0d0m0.0s', Longitude(0, unit=u.degree)),
        ('-0d0m0.0s', Longitude(0, unit=u.degree)),
        ('+0d0m0.0s', Longitude(0, unit=u.degree)),
    ]
    declinations = [
        ('22d42m39.0645', Latitude('22d42m39.0645', unit=u.degree)),
        ('+22d42m39.0645', Latitude('22d42m39.0645', unit=u.degree)),
        ('-22d42m39.0645', Latitude('-22d42m39.0645', unit=u.degree)),
        ('0d0m0.0s', Latitude(0, unit=u.degree)),
        ('+0d0m0.0s', Latitude(0, unit=u.degree)),
        ('-0d0m0.0s', Latitude(0, unit=u.degree)),
    ]

    for name in names:
        for ra_str, ra in right_ascensions:
            for dec_str, dec in declinations:
                field = Field(name, '%s %s' % (ra_str, dec_str), config_port=config_port)
                assert field.name == name
                assert field.coord.ra == ra
                assert field.coord.dec == dec
