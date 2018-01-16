import numpy as np
from scipy import interpolate


class Horizon(object):
    """A simple class to define some coordinate points.

    Accepts a list of tuples where each tuple consists of two points corresponding
    to an altitude (0-90) and an azimuth (0-360). If azimuth is a negative number
    (but greater than -360) then 360 will be added to put it in the correct
    range.

    The list are points that are obstruction points beyond the default horizon.
    """

    def __init__(self, obstructions=list(), base_horizon=30.):
        """Create a list of horizon obstruction points

        Args:
            points (list[tuple(float, float)]): A list of length 2 tuples corresponding
                to az/alt points.

        """
        super().__init__()

        obstruction_list = list()
        for obstruction in obstructions:
            assert isinstance(obstruction, tuple), "Obstructions must be tuples"
            assert len(obstruction) >= 2, "Obstructions must have at least 2 points"

            obstruction_line = list()
            for point in obstruction:
                assert isinstance(point, tuple), "Obstruction points must be tuples"
                assert len(point) == 2, "Obstruction points must be 2 points"

                assert type(point[0]) is not bool, "Bool not allowed"
                assert type(point[1]) is not bool, "Bool not allowed"
                assert isinstance(point[0], (float, int, np.integer)), "Must be number-like"
                assert isinstance(point[1], (float, int, np.integer)), "Must be number-like"

                alt = float(point[0])
                az = float(point[1])

                assert 0. <= alt <= 90., "Altitude must be between 0-90 degrees"

                if az < 0.:
                    az += 360

                assert 0. <= az <= 360., "Azimuth must be between 0-360 degrees"
                obstruction_line.append((alt, az))
            obstruction_list.append(sorted(obstruction_line, key=lambda point: point[1]))

        self.obstructions = sorted(obstruction_list, key=lambda point: point[1])

        self.horizon_line = np.ones(360) * base_horizon

        # Make helper lists of the alt and az
        self.alt = list()
        self.az = list()
        for obstruction in self.obstructions:
            self.alt.append([point[0] for point in obstruction])
            self.az.append([point[1] for point in obstruction])

        for obs_az, obs_alt in zip(self.az, self.alt):
            f = interpolate.interp1d(obs_az, obs_alt)

            x_range = np.arange(obs_az[0], obs_az[-1] + 1)
            new_y = f(x_range)

            # Assign over index elements
            for i, j in enumerate(x_range):
                self.horizon_line[int(j)] = new_y[i]

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
