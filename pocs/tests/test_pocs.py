import pytest

from pocs import POCS


@pytest.fixture(scope='module')
def pocs():
    pocs = POCS(simulator=['all'])
    return pocs


def test_simple_simulator(pocs):
    assert isinstance(pocs, POCS)


def test_not_initialized(pocs):
    assert pocs.is_initialized is not True


def test_run_without_initilize(pocs):
    with pytest.raises(AssertionError):
        pocs.run()


def test_initialization(pocs):
    pocs.initialize()
    assert pocs.is_initialized
