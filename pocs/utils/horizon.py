import numpy as np
from scipy import interpolate


class Horizon(object):
    """A simple class to define some coordinate points.

    Accepts a list of lists where each list consists of two points corresponding
    to an altitude (0-90) and an azimuth (0-360). If azimuth is a negative number
    (but greater than -360) then 360 will be added to put it in the correct
    range.

    The list are points that are obstruction points beyond the default horizon.
    """

    def __init__(self, obstructions=list(), default_horizon=30):
        """Create a list of horizon obstruction points.

        Example:
            An example `obstruction_point` list:
            ```
            [
                [[40, 30], [40, 75]],   # From azimuth 30° to 75° there is an
                                        # obstruction that is at 40° altitude
                [[50, 180], [40, 200]], # From azimuth 180° to 200° there is
                                        # an obstruction that slopes from 50°
                                        # to 40° altitude
            ]
            ```

        Args:
            obstructions (list(list(list)), optional): A list of obstructions
                where each obstruction consists of a set of lists. The individual
                lists are alt/az pairs. Defaults to empty list in which case the
                `default_horizon` defines a flat horizon.
            default_horizon (float, optional): A default horizon to be used whenever
                there is no obstruction.

        """
        super().__init__()

        obstruction_list = list()
        for obstruction in obstructions:
            assert isinstance(obstruction, list), "Obstructions must be lists"
            assert len(obstruction) >= 2, "Obstructions must have at least 2 points"

            obstruction_line = list()
            for point in obstruction:
                assert isinstance(point, list), "Obstruction points must be lists"
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

        self.default_horizon = default_horizon
        self.horizon_line = np.ones(360) * self.default_horizon

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
