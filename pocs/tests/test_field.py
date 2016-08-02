import pytest

from astropy import units as u
from pocs.scheduler.field import Field


def test_create_field_no_params():
    with pytest.raises(TypeError):
        Field()


def test_create_field_bad_position():
    with pytest.raises(ValueError):
        Field("TestField", "Bad Position")


def test_create_field_bad_priority():
    with pytest.raises(AssertionError):
        Field('TestField', '20h00m43.7135s +22d42m39.0645s', priority=0)
        Field('TestField', '20h00m43.7135s +22d42m39.0645s', priority=-1)


def test_create_field_exp_time_no_units():
    with pytest.raises(TypeError):
        Field('TestField', '20h00m43.7135s +22d42m39.0645s', exp_time=1.0)


def test_create_field_exp_time_bad():
    with pytest.raises(AssertionError):
        Field('TestField', '20h00m43.7135s +22d42m39.0645s', exp_time=0.0 * u.second)


def test_create_field_exp_time_minutes():
    field = Field('TestField', '20h00m43.7135s +22d42m39.0645s', exp_time=5.0 * u.minute)
    assert field.exp_time == 300 * u.second


def test_create_field_default_duration():
    field = Field('TestField', '20h00m43.7135s +22d42m39.0645s')
    assert field.duration == 120 * u.second


def test_create_field_default_exptime():
    field = Field('TestField', '20h00m43.7135s +22d42m39.0645s')
    assert field.exp_time == 120 * u.second


def test_create_field_good_priority():
    field = Field('TestField', '20h00m43.7135s +22d42m39.0645s', priority=5.0)
    assert field.priority == 5.0


def test_create_field_priority_str():
    field = Field('TestField', '20h00m43.7135s +22d42m39.0645s', priority="5")
    assert field.priority == 5.0


def test_create_field_name():
    field = Field('Test field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.name == 'Test field - 32b'


def test_create_field_field_name():
    field = Field('Test field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.field_name == 'TestField32B'
