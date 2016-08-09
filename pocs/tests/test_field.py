import pytest

from pocs.scheduler.field import Field


def test_create_field_no_params():
    with pytest.raises(TypeError):
        Field()


def test_create_field_bad_position():
    with pytest.raises(ValueError):
        Field("TestObservation", "Bad Position")


def test_create_field_bad_priority():
    with pytest.raises(AssertionError):
        Field('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=0)
        Field('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=-1)


def test_create_field_good_priority():
    field = Field('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority=5.0)
    assert field.priority == 5.0


def test_create_field_priority_str():
    field = Field('TestObservation', '20h00m43.7135s +22d42m39.0645s', priority="5")
    assert field.priority == 5.0


def test_create_field_name():
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.name == 'Test Field - 32b'


def test_create_field_Observation_name():
    field = Field('Test Field - 32b', '20h00m43.7135s +22d42m39.0645s')
    assert field.field_name == 'TestField32B'
