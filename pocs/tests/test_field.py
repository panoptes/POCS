import pytest

from pocs.scheduler.field import Field


def test_create_field_no_params():
    with pytest.raises(TypeError):
        Field()


def test_create_field_bad_position():
    with pytest.raises(ValueError):
        Field("TestObservation", "Bad Position")


def test_create_field_name():
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.name == 'Test Field - 32b'


def test_equinox_none():
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s', equinox=None)
    assert field.coord.equinox == 'J2000'


def test_create_field_Observation_name():
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.field_name == 'TestField32B'
