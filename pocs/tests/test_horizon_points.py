import pytest
import numpy as np
import random

from panoptes.utils.horizon import Horizon


def test_normal():
    hp = Horizon(obstructions=[
        [[20, 10], [40, 70]]
    ])
    assert isinstance(hp, Horizon)

    hp2 = Horizon(obstructions=[
        [[40, 45], [50, 50], [60, 45]]
    ])
    assert isinstance(hp2, Horizon)

    hp3 = Horizon()
    assert isinstance(hp3, Horizon)


def test_bad_length_tuple():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            [[20], [40, 70]]
        ])


def test_bad_length_list():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            [[40, 70]]
        ])


def test_bad_string():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            [["x", 10], [40, 70]]
        ])


def test_too_many_points():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[[[120, 60, 300]]])


def test_wrong_bool():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[[[20, 200], [30, False]]])


def test_numpy_ints():
    range_length = 360
    points = [list(list(a) for a in zip(
        [random.randrange(15, 50) for _ in range(range_length)],  # Random height
        np.arange(1, range_length, 25)  # Set azimuth
    ))]
    points
    assert isinstance(Horizon(points), Horizon)


def test_negative_alt():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            [[10, 20], [-1, 30]]
        ])


def test_good_negative_az():
    hp = Horizon(obstructions=[
        [[50, -10], [45, -20]]
    ])
    assert isinstance(hp, Horizon)

    hp2 = Horizon(obstructions=[
        [[10, -181], [20, -190]]
    ])
    assert isinstance(hp2, Horizon)


def test_bad_negative_az():
    with pytest.raises(AssertionError):
        Horizon(obstructions=[
            [[10, -361], [20, -350]]
        ])


def test_sorting():
    points = [
        [[10., 10.], [20., 20.]],
        [[30., 190.], [10., 180.]],
        [[10., 50.], [30., 60.]],
    ]
    hp = Horizon(obstructions=points)
    assert hp.obstructions == [[(10.0, 10.0), (20.0, 20.0)],
                               [(10.0, 50.0), (30.0, 60.0)],
                               [(10.0, 180.0), (30.0, 190.0)]]
