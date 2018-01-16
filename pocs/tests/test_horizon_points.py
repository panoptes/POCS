import pytest

from pocs.utils.images.horizon import HorizonPoints, get_altitude


def test_normal():
    hp = HorizonPoints(points=[(20, 10), (40, 70)])
    assert isinstance(hp, HorizonPoints)

    hp2 = HorizonPoints(points=[(40, 10)])
    assert isinstance(hp2, HorizonPoints)


def test_bad_string():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[("x", 10), (40, 70)])


def test_bad_length_tuple():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[(20), (40, 70)])


def test_no_points():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[])


def test_too_many_points():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[(120, 60, 300)])


def test_wrong_bool():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[(200, False)])


def test_negative_alt():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[(-1, 20)])


def test_good_negative_az():
    hp = HorizonPoints(points=[(50, -10)])
    assert isinstance(hp, HorizonPoints)

    hp2 = HorizonPoints(points=[(10, -181)])
    assert isinstance(hp2, HorizonPoints)


def test_bad_negative_az():
    with pytest.raises(AssertionError):
        HorizonPoints(points=[(10, -361)])


def test_sorting():
    points = [(10., 10.), (90., 20.), (5., 5.)]
    hp = HorizonPoints(points=points)
    assert hp.points == sorted(points)


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
