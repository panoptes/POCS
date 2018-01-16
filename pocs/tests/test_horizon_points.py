import pytest
import numpy as np
import random

from pocs.utils.images.horizon import Horizon, get_altitude


def test_normal():
    hp = Horizon(obstructions=[
        ((20, 10), (40, 70))
    ])
    assert isinstance(hp, Horizon)

    hp2 = Horizon(obstructions=[
        ((40, 45), (50, 50), (60, 45))
    ])
    assert isinstance(hp2, Horizon)

    hp3 = Horizon()
    assert isinstance(hp3, Horizon)


def test_bad_length_tuple():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            ((20), (40, 70))
        ])


def test_bad_length_list():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            ((40, 70))
        ])


def test_bad_string():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            (("x", 10), (40, 70))
        ])


def test_too_many_points():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[((120, 60, 300))])


def test_wrong_bool():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[((20, 200), (30, False))])


def test_numpy_ints():
    range_length = 360
    points = [tuple(zip(
        [random.randrange(15, 50) for _ in range(range_length)],  # Random height
        np.arange(1, range_length, 25)  # Set azimuth
    ))]
    points
    assert isinstance(Horizon(points), Horizon)


def test_negative_alt():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            ((10, 20), (-1, 30))
        ])


def test_good_negative_az():
    hp = Horizon(obstructions=[
        ((50, -10), (45, -20))
    ])
    assert isinstance(hp, Horizon)

    hp2 = Horizon(obstructions=[
        ((10, -181), (20, -190))
    ])
    assert isinstance(hp2, Horizon)


def test_bad_negative_az():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            ((10, -361), (20, -350))
        ])


def test_sorting():
    points = [
        ((10., 10.), (20., 20.)),
        ((30., 190.), (10., 180.)),
        ((10., 50.), (30., 60.)),
    ]
    hp = Horizon(obstructions=points)
    assert hp.obstructions == [[(10.0, 10.0), (20.0, 20.0)],
                               [(10.0, 50.0), (30.0, 60.0)],
                               [(10.0, 180.0), (30.0, 190.0)]]


def test_get_altitude_flat():
    assert get_altitude((20, 20), (25, 20), 25) == 20


def test_get_altitude_vertical():
    assert get_altitude((20, 20), (20, 25), 20) == 25


def test_get_altitude_invalid_az():
    with pytest.raises(AssertionError):
        assert get_altitude((20, 20), (20, 25), 30) == 25


def test_get_altitude_slope():
    # Testing if the azimuth is between 2 obstruction points (using interpolate)
    assert get_altitude((20, 20), (25, 25), 22) == 22


def test_get_altitude_fail():
    # Testing if the azimuth isn't an obstruction point (using interpolate)
    with pytest.raises(AssertionError):
        assert get_altitude((20, 20), (25, 25), 22) == 0


# def test_determine_el():

#     Horizon1 = Horizon()
#     Horizon1.set_obstruction_points([(20, 20), (25, 20)])

#     # Testing if the azimuth is already an obstruction point (2 points)
#     assert Horizon1.determine_el(25) == 20

#     Horizon1.set_obstruction_points([(20, 20), (25, 20), (30, 30)])

#     # Testing if the azimuth is already an obstruction point (3 points)
#     assert Horizon1.determine_el(25) == 20

#     # Testing if the azimuth is an obstruction point (using interpolate)
#     assert Horizon1.determine_el(22) == 20

#     # Testing an azimuth before the first obstruction point
#     assert Horizon1.determine_el(10) == 0

#     # Testing if the azimuth isn't an obstruction point (using interpolate)
#     with pytest.raises(AssertionError):
#         assert Horizon1.determine_el(23) == 100


# def test_get_config_coords():

#     Horizon1 = Horizon()
#     Horizon1.get_config_coords()

#     assert Horizon1.obstruction_points == [(10, 10), (20, 20), (340, 70), (350, 80)]
