# from skimage.io import imread
# from skimage.filters import threshold_otsu
# from skimage import feature
# import numpy as np


class HorizonPoints(object):
    """A simple class to define some coordinate points.

    Accepts a list of points where each point is a tuple consisting of
    an azimuth (0-360) and altitude (0-90). If azimuth is a negative number
    (but greater than -360) then 360 will be added to put it in the correct
    range.
    """

    def __init__(self, points):
        """Create a list of horizon obstruction points

        Args:
            points (list[tuple(float, float)]): A list of length 2 tuples corresponding
                to az/alt points.

        """
        super(HorizonPoints, self).__init__()

        assert len(points) > 0, "Must pass at least one set of points"

        valid_points = list()
        for point in points:
            assert isinstance(point, tuple)
            assert len(point) == 2

            assert type(point[0]) in [float, int]
            assert type(point[1]) in [float, int]

            alt = float(point[0])
            az = float(point[1])

            assert 0. <= alt <= 90., "Altitude must be between 0-90 degrees"

            if az < 0.:
                az += 360

            assert 0. <= az <= 360., "Azimuth must be between 0-360 degrees"
            valid_points.append((alt, az))

        self.points = sorted(valid_points)

    # def determine_alt(self, az):
    #     """
    #     # Determine if the target altitude is above or below the
    #     determined minimum elevation for that azimuth.

    #     Args:
    #         az (float or int): the target azimuth
    #     """

    #     el = 0
    #     prior_point = self.obstruction_points[0]
    #     i = 1
    #     found = False
    #     for i, point in enumerate(self.obstruction_points):
    #         if found:
    #             break
    #         elif az >= prior_point[0] and az <= point[0]:
    #             el = self.interpolate(prior_point, point, az)
    #             found = True
    #         else:
    #             i += 1
    #             prior_point = point
    #     return el


def get_altitude(point_a, point_b, az):
    """Get a line from the given horizon points.

    Determine the line equation between two points to return the
    altitude for a given azimuth.

    Note: The desired az must be within the range of given points.

    Args:
        point_a (tuple): obstruction point A.
        point_b (tuple): obstruction point B.
        az (float or int): the target azimuth for which we want to determine
            an altitude
    """

    x1, y1 = point_a
    x2, y2 = point_b

    assert x1 <= az <= x2, "Can't determine azimuth outside of ranage of points"

    if x2 == x1:  # Vertical Line
        alt = max(y1, y2)
    else:
        m = ((y2 - y1) / (x2 - x1))
        b = y1 - m * x1
        alt = m * az + b

    assert alt <= 90

    return alt


# def find_horizon_edges(self, image_filename):
#     """
#     Process the horizon_image to generate the obstruction_points list
#     Segment regions of high contrast using scikit image
#     Image Segmentation with Watershed Algorithm
#     bottom_left is a tuple, top_right is a tuple, each tuple has az, el
#     to allow for incomplete horizon images

#     Note:
#         Incomplete method, further work to be done to automate the horizon limits

#     Args:
#         image_filename (file): The horizon panorama image to be processed
#     """

#     image = imread(image_filename, flatten=True)
#     thresh = threshold_otsu(image)
#     binary = image > thresh

#     # Compute the Canny filter
#     edges1 = feature.canny(binary, low_threshold=0.1, high_threshold=0.5)

#     # Turn into array
#     np.set_printoptions(threshold=np.nan)
#     print(edges1.astype(np.float))
