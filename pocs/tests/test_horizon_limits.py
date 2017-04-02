import pytest

from pocs.scheduler.constraint import Horizon

"""
Validation tests, fail if: 
1.	If there are no points
2.	If there is only one point
3.	If any point doesnt have two components (az and el)
4.	If any point is the incorrect data type
5.	If any point isnt in the azimuth range (0<=azimuth<359,59,59) 
6.	If any point isnt in the elevation range (0<=elevation<90) 
7.	If any inputted azimuth isnt in the correct sequence low and increasing order, so if a subsequent azimuth is less than a previous one
8.	If multiple data points have the same azimuth thrice or more if two azimuths are equal it defines a vertical line 
9. Make the obstructions are a reasonable size - no zero to 360 case

Test case	Test no.	Test Case	Validation pass/fail
1	1	No points	F
2	2	One point (10, 50)	F
3	3	Two points (100, 50), (120)	F
4	3	Two points (100, 50, 50) (120, 60)	F
5	3	Two points (100), (120, 60)	F
6	3	Two points (100), (120)	F
7	4	A string: test	F
8	4	A boolean: true	F
9	4	(x,20), (120, 60)	F
10	4	(10, 50), (30, 10y)	F
11	5	Two points: (-2, 60), (-1, 70)	F
12	5	Two points: (-1, 60), (1, 70)	F
13	6	Two points: (20, -2), (40, -1) 	F
14	6	Two points: (20, -2), (40, 70)	F
15	7	Two points: (50, 60), (40, 70)	F
16	8	Three points: (50, 60), (50, 70), (50, 80)	F
"""

#1.	If there are no points
"""
def test_validation_1(obstruction_points):
	#Using the implicit booleanness of the empty list
	assert obstruction_points 
"""

def test_validation_1(obstruction_points):
	#Using the implicit booleanness of the empty list
	return len(obstruction_points)>0 

#2.	If there is only one point
def test_validation_2(obstruction_points):
 	assert len(obstruction_points)>=2

#3.	If any point doesnt have two components (az and el)
def test_validation_3(obstruction_points):
	for i in obstruction_points:
		assert len(i)==2
 
#4.	If any point is the incorrect data type
def test_validation_4(obstruction_points):
	assert type(obstruction_points)==list
	for i in obstruction_points:
		assert type(i[0])==float 
		assert type(i[1])==float

#5.	If any point isnt in the azimuth range (0<=azimuth<359,59,59) 
def test_validation_5(obstruction_points):
	for i in obstruction_points:
		az = i[0] 
		assert az>=0 and az<2*math.pi #degrees are astropy units degrees - radians

#6.	If any point isnt in the elevation range (0<=elevation<90) 
def test_validation_6(obstruction_points):
	for i in obstruction_points:
		el = i[1] 
		assert el>=0 and el<(math.pi)/2

#7.	If any inputted azimuth isnt in the correct sequence low and increasing order
def test_validation_7(obstruction_points):
	az_list = []
	for i in obstruction_points:
		az_list.append(i[0])
	assert sorted(az_list) == az_list

#8.	If multiple data points have the same azimuth thrice or more if two azimuths are equal it defines a vertical line 
def test_validation_8(obstruction_points):
	from itertools import groupby
	az_list = []
	for i in obstruction_points:
		az_list.append(i[0])
		assert [len(list(group)) for key, group in groupby(az_list)]<=2
		
optc1=[]
optc2=[(10, 50)]
optc3=[(100, 50), (120)]
optc4=[(100, 50, 50), (120, 60)]
optc5=[(100), (120, 60)]
optc6=[(100), (120)]
optc7=["test"]
optc8=[True]
optc9=[("x",20), (120, 60)]
optc10=[(10, 50), (30, "10y")]
optc11=[(-2, 60), (-1, 70)]
optc12=[(-1, 60), (1, 70)]
optc13=[(20, -2), (40, -1)]
optc14=[(20, -2), (40, 70)]
optc15=[(50, 60), (40, 70)]
optc16=[(50, 60), (50, 70), (50, 80)]

obstruction_points_test_cases=[optc1, optc2, optc3, optc4, optc5, optc6, optc7, optc8, optc9, 
								optc10, optc11, optc12, optc13, optc14, optc15, optc16]


assert test_validation_1(optc1) == False

#test_validation_2(optc1)

"""
[
[(x0, y0), (x1, y1), (x1, y2)]
[(x0, y0), (x1, y1), (x1, y2)]
]
"""

"""
def test_validations():
	test_validation_1()
	test_validation_2()
	test_validation_3()
	test_validation_4()
	test_validation_5()
	test_validation_6()
	test_validation_7()
	test_validation_8()
"""

def test_interpolate():

	Horizon1 = Horizon()

	#Testing if the azimuth is already an obstruction point
	assert Horizon1.interpolate((20, 20), (25, 20), 25) == 20

	#Testing if the azimuth isn't an obstruction point (using interpolate)
	assert Horizon1.interpolate((20, 20), (25, 25), 22) == 22

	#Testing if the azimuth isn't an obstruction point (using interpolate)
	assert Horizon1.interpolate((20, 20), (25, 25), 22) == 0

def test_determine_el():

	Horizon1 = Horizon()

	#Testing if the azimuth is already an obstruction point (2 points)
	assert Horizon1.determine_el([(20, 20), (25, 20), (30, 30)], 25) == 20

	#Testing if the azimuth is already an obstruction point (3 points)
	assert Horizon1.determine_el([(20, 20), (25, 20), (30, 30)], 25) == 20

	#Testing if the azimuth isn't an obstruction point (using interpolate)
	assert Horizon1.determine_el([(20, 20), (25, 25)], 22) == 22

def test_horizon_limits():
	#test_validations()
	test_interpolate()
	test_determine_el()





