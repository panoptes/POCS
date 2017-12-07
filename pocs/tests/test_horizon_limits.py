import pytest

from pocs.scheduler.constraint import Horizon


#       If there is only one point
def validation_1(obstruction_points):
    assert len(obstruction_points) >= 2


#       If any point isn't a tuple, if any tuple isn't of length 2
def validation_2(obstruction_points):
    for i in obstruction_points:
        assert type(i) == tuple
        assert len(i) == 2


#       If any point is the incorrect data type
def validation_3(obstruction_points):
    assert type(obstruction_points) == list
    for i in obstruction_points:
        assert type(i[0]) == float or type(i[0]) == int
        assert type(i[1]) == float or type(i[1]) == int


#       If any point isnt in the azimuth range (0<=azimuth<359,59,59)
def validation_4(obstruction_points):
    for i in obstruction_points:
        az = i[0]
        assert az >= 0 and az < 360  # degrees are astropy units degrees


#       If any point isnt in the elevation range (0<=elevation<90)
def validation_5(obstruction_points):
    for i in obstruction_points:
        el = i[1]
        assert el >= 0 and el <= 90


#       If any inputted azimuth isnt in the correct sequence low and increasing order
def validation_6(obstruction_points):
    az_list = []
    for i in obstruction_points:
        az_list.append(i[0])
    assert sorted(az_list) == az_list


#       If multiple data points have the same azimuth thrice or more
#       This works assuming that the array is sorted as per validation_6
def validation_7(obstruction_points):
    azp1 = -1
    azp2 = -1
    for i in obstruction_points:
        az = i[0]
        assert az != azp1 or azp1 != azp2
        azp2 = azp1
        azp1 = az


def obstruction_points_valid(obstruction_points):
    v = True
    try:
        validation_1(obstruction_points)
    except AssertionError:
        print("obstruction_points should have at least 2 sets of points")
        v = False
    try:
        validation_2(obstruction_points)
    except AssertionError:
        print("Each point should have 2 of components (az and el")
        v = False
    try:
        validation_3(obstruction_points)
    except AssertionError:
        print("obstruction_points should be a list of tuples where each element is a float or an int")
        v = False
    try:
        validation_4(obstruction_points)
    except AssertionError:
        print("obstruction_points should be in the azimuth range of 0 <= azimuth < 60")
        v = False
    try:
        validation_5(obstruction_points)
    except AssertionError:
        print("obstruction_points should be in the elevation range of 0 <= elevation < 90")
        v = False
    try:
        validation_6(obstruction_points)
    except AssertionError:
        print("obstruction_points azimuth's should be in an increasing order")
        v = False
    try:
        validation_7(obstruction_points)
    except AssertionError:
        print("obstruction_points should not consecutively have the same azimuth thrice or more")
        v = False
    assert v
    return v


# Unit tests for each of the evaluations
def test_validations():

    validation_1([(20, 10), (40, 70)])
    validation_1([("x", 10), (40, 70)])
    validation_1([(20), (40, 70)])
    with pytest.raises(AssertionError):
        validation_1([])
    with pytest.raises(AssertionError):
        validation_1([10])
    with pytest.raises(AssertionError):
        validation_1([(30, 20)])

    validation_2([])
    validation_2([(20, 10)])
    validation_2([(10, 10), (40, 70)])
    validation_2([("x", 10), (40, 70)])
    validation_2([("x", 10), (40, 70), (50, 80)])
    with pytest.raises(AssertionError):
        validation_2([(100), (120, 60)])
    with pytest.raises(AssertionError):
        validation_2([(120, 60), (100)])
    with pytest.raises(AssertionError):
        validation_2([(120, 60, 300)])
    with pytest.raises(AssertionError):
        validation_2([(120, 60, 300), (120, 60)])

    validation_3([(120, 300)])
    validation_3([(10, 10), (40, 70)])
    with pytest.raises(AssertionError):
        validation_3([("x", 300)])
    with pytest.raises(AssertionError):
        validation_3([(200, False)])
    with pytest.raises(AssertionError):
        validation_3([[(200, 99)]])
    with pytest.raises(AssertionError):
        validation_3([((1, 2), 2)])

    validation_4([(20, -2), (40, 70)])
    validation_4([(20, 20), (40, 70)])
    validation_4([(359.9, 20), (40, 70)])
    validation_4([(20, 20), (40, 0.01)])
    validation_4([(0, 20), (40, 50)])
    with pytest.raises(AssertionError):
        validation_4([(-1, 65), (1, 70)])
    with pytest.raises(AssertionError):
        validation_4([(50, 60), (-10, 70)])
    with pytest.raises(AssertionError):
        validation_4([(370, 60), (1, 70)])
    with pytest.raises(AssertionError):
        validation_4([(350, 60), (800, 70)])
    with pytest.raises(AssertionError):
        validation_4([(360.01, 60), (200, 70)])
    with pytest.raises(AssertionError):
        validation_4([(-0.01, 60), (200, 70)])
    with pytest.raises(AssertionError):
        validation_4([(360, 60), (200, 70)])

    validation_5([(40, 70), (-20, 2)])
    validation_5([(40, 70), (20, 20)])
    validation_5([(40, 70), (359.9, 20)])
    validation_5([(40, 0.01), (20, 20)])
    validation_5([(40, 50), (0, 20)])
    with pytest.raises(AssertionError):
        validation_5([(1, 70), (1, -65)])
    with pytest.raises(AssertionError):
        validation_5([(10, -70), (50, 60)])
    with pytest.raises(AssertionError):
        validation_5([(1, 70), (350, 370)])
    with pytest.raises(AssertionError):
        validation_5([(80, 700), (350, 60)])
    with pytest.raises(AssertionError):
        validation_5([(200, 70), (359, 360.01)])
    with pytest.raises(AssertionError):
        validation_5([(200, 70), (60, -0.01)])
    with pytest.raises(AssertionError):
        validation_5([(200, 70), (350, 360)])

    validation_6([(10, 20)])
    validation_6([(40, 70), (50, 60)])
    validation_6([(40, 70), (40, 60)])
    validation_6([(50, 60), (60, 70), (70, 50)])
    with pytest.raises(AssertionError):
        validation_6([(50, 60), (40, 70)])
    with pytest.raises(AssertionError):
        validation_6([(50, 60), (60, 70), (40, 50)])

    validation_7([(50, 60), (60, 70), (70, 50)])
    validation_7([(50, 60), (60, 70)])
    with pytest.raises(AssertionError):
        validation_7([(50, 60), (50, 70), (50, 80)])
    with pytest.raises(AssertionError):
        validation_7([(50, 60), (50, 70), (50, 80), (50, 80)])

    # The following tests test the whole test suite and are designed to pass
    obstruction_points_valid([(20, 10), (40, 70)])
    obstruction_points_valid([(50, 60), (60, 70), (70, 50)])
    obstruction_points_valid([(10, 10), (40, 70), (50, 30), (65, 10)])
    obstruction_points_valid([(10, 10), (40, 70), (50, 30), (65, 10), (85, 85)])

    # The following tests test the whole test suite and are designed to fail
    with pytest.raises(AssertionError):
        obstruction_points_valid([])
    with pytest.raises(TypeError):
        obstruction_points_valid([("x", 300)])
    with pytest.raises(AssertionError):
        obstruction_points_valid([(-1, 65), (1, 70)])
    with pytest.raises(AssertionError):
        obstruction_points_valid([(1, 70), (1, -65)])
    with pytest.raises(AssertionError):
        obstruction_points_valid([(50, 60), (40, 70)])
    with pytest.raises(AssertionError):
        obstruction_points_valid([(50, 60), (50, 70), (50, 80)])


def test_interpolate():

    Horizon1 = Horizon()

    # Testing if the azimuth is already an obstruction point
    assert Horizon1.interpolate((20, 20), (25, 20), 25) == 20

    # Testing if the azimuth is already an obstruction point
    assert Horizon1.interpolate((20, 20), (25, 20), 25) == 20

    # Testing if the azimuth is between 2 obstruction points (using interpolate)
    assert Horizon1.interpolate((20, 20), (25, 25), 22) == 22

    # Testing if the azimuth isn't an obstruction point (using interpolate)
    with pytest.raises(AssertionError):
        assert Horizon1.interpolate((20, 20), (25, 25), 22) == 0


def test_determine_el():

    Horizon1 = Horizon()
    Horizon1.set_obstruction_points([(20, 20), (25, 20)])

    # Testing if the azimuth is already an obstruction point (2 points)
    assert Horizon1.determine_el(25) == 20

    Horizon1.set_obstruction_points([(20, 20), (25, 20), (30, 30)])

    # Testing if the azimuth is already an obstruction point (3 points)
    assert Horizon1.determine_el(25) == 20

    # Testing if the azimuth is an obstruction point (using interpolate)
    assert Horizon1.determine_el(22) == 20

    # Testing an azimuth before the first obstruction point
    assert Horizon1.determine_el(10) == 0

    # Testing if the azimuth isn't an obstruction point (using interpolate)
    with pytest.raises(AssertionError):
        assert Horizon1.determine_el(23) == 100


def test_get_config_coords():

    Horizon1 = Horizon()
    Horizon1.get_config_coords()

    assert Horizon1.obstruction_points == [(10, 10), (20, 20), (340, 70), (350, 80)]
