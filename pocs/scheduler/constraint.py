from astropy import units as u

from pocs import PanBase


class BaseConstraint(PanBase):

    def __init__(self, weight=1.0, default_score=0.0, *args, **kwargs):
        """ Base constraint

        Each constraint consists of a `get_score` method that is responsible
        for determining a score for a particular target and observer at a given
        time. The `score` is then multiplied by the `weight` of the constraint.

        Args:
            weight (float, optional): The weight of the observation, which will
                be multipled by the score
            default_score (float, optional): The starting score for observation
            *args (TYPE): Description
            **kwargs (TYPE): Description
        """
        super(BaseConstraint, self).__init__(*args, **kwargs)

        assert isinstance(weight, float), \
            self.logger.error(
                "Constraint weight must be a float greater than 0.0")
        assert weight >= 0.0, \
            self.logger.error(
                "Constraint weight must be a float greater than 0.0")

        self.weight = weight
        self._score = default_score

    def get_score(self, time, observer, target):
        raise NotImplementedError


class Altitude(BaseConstraint):

    """ Simple Altitude Constraint

    A simple altitude constraint that determines if the given `observation` is
    above a minimum altitude.

    Note:
        This functionality can also be accomplished more directly with the
        `Duration` constraint

    Attributes:
        minimum (u.degree): The minimum acceptable altitude at which to observe
    """
    @u.quantity_input(minimum=u.degree)
    def __init__(self, minimum, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.minimum = minimum

    def get_score(self, time, observer, observation, **kwargs):
        target = observation.field

        alt = observer.altaz(time, target=target).alt

        veto = False
        score = self._score

        if alt < self.minimum:
            veto = True

        if alt >= self.minimum:
            score = 1.0

        return veto, score * self.weight

    def __str__(self):
        return "Altitude {}".format(self.minimum)


class Duration(BaseConstraint):

    @u.quantity_input(horizon=u.degree)
    def __init__(self, horizon, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.horizon = horizon

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        target = observation.field

        veto = not observer.target_is_up(time, target, horizon=self.horizon)

        end_of_night = kwargs.get('end_of_night',
                                  observer.tonight(time=time, horizon=-18 * u.degree)[1])

        if not veto:
            # Get the next meridian flip
            target_meridian = observer.target_meridian_transit_time(
                time, target,
                which='next')

            # If it flips before end_of_night it hasn't flipped yet so
            # use the meridian time as the end time
            if target_meridian < end_of_night:

                # If target can't meet minimum duration before flip, veto
                if time + observation.minimum_duration > target_meridian:
                    self.logger.debug(
                        "Observation minimum can't be met before meridian flip")
                    veto = True

            # else:
            # Get the next set time
            target_end_time = observer.target_set_time(
                time, target,
                which='next',
                horizon=self.horizon)

            # If end_of_night happens before target sets, use end_of_night
            if target_end_time > end_of_night:
                self.logger.debug(
                    "Target sets past end_of_night, using end_of_night")
                target_end_time = end_of_night

            # Total seconds is score
            score = (target_end_time - time).sec
            if score < observation.minimum_duration.value:
                veto = True

            # Normalize the score based on total possible number of seconds
            score = score / (end_of_night - time).sec

        return veto, score * self.weight

    def __str__(self):
        return "Duration above {}".format(self.horizon)


class MoonAvoidance(BaseConstraint):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_score(self, time, observer, observation, **kwargs):
        veto = False
        score = self._score

        try:
            moon = kwargs['moon']
        except KeyError:
            self.logger.error("Moon must be set")

        moon_sep = moon.separation(observation.field.coord).value

        # This would potentially be within image
        if moon_sep < 15:
            self.logger.debug("Moon separation: {}".format(moon_sep))
            veto = True
        else:
            score = (moon_sep / 180)

        return veto, score * self.weight

    def __str__(self):
        return "Moon Avoidance"


class Horizon(BaseConstraint):

    """ Implements horizon and obstruction limits"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.obstruction_points = []

        print("Horizon.__init__")
        for i in self.config:
            print(i, self.config[i])

    def set_obstruction_points(self, op):
        self.obstruction_points = op

    def process_image(self, image_filename):
        """
        Process the horizon_image to generate the obstruction_points list
        Segment regions of high contrast using scikit image
        Image Segmentation with Watershed Algorithm
        bottom_left is a tuple, top_right is a tuple, each tuple has az, el
        to allow for incomplete horizon images

        Note:
            Incomplete method, further work to be done to automate the horizon limits

        Args:
            image_filename (file): The horizon panorama image to be processed
        """

        from skimage.io import imread
        from skimage.filters import threshold_otsu
        from skimage import feature
        import numpy as np

        image = imread(image_filename, flatten=True)
        thresh = threshold_otsu(image)
        binary = image > thresh

        # Compute the Canny filter
        edges1 = feature.canny(binary, low_threshold=0.1, high_threshold=0.5)

        # Turn into array
        np.set_printoptions(threshold=np.nan)
        print(edges1.astype(np.float))

    def get_config_coords(self):
        """
        Retrieves the coordinate list from the config file and validates it
        If valid sets up a value for obstruction_points, otherwise leaves it empty
        """

        from pocs.tests.test_horizon_limits import obstruction_points_valid

        self.obstruction_points = self.config['location']['horizon_constraint']

        print("get_config_coords", "obstruction_points", self.obstruction_points)

        if not obstruction_points_valid(self.obstruction_points):
            self.obstruction_points = []

    def enter_coords(self):
        """
        Enters a coordinate list from the user and validates it
        If valid sets up a value for obstruction_points, otherwise leaves it empty
        """

        from pocs.tests.test_horizon_limits import obstruction_points_valid
        print("Enter a list of azimuth elevation tuples with increasing azimuths.")
        print("For example (10,10), (20,20), (340,70), (350,80)")

        self.obstruction_points = input()
        if not obstruction_points_valid(self.obstruction_points):
            self.obstruction_points = []

    def interpolate(self, A, B, az):
        """
        Determine the line equation between two points to return the elevation for a given azimuth

        Args:
            A (tuple): obstruction point A
            B (tuple): obstruction point B
            az (float or int): the target azimuth
        """

        # Input validation assertions.
        assert len(A) == 2
        assert len(B) == 2
        assert type(az) == float or type(az) == int
        assert type(A[0]) == float or type(A[0]) == int
        assert type(A[1]) == float or type(A[1]) == int
        assert type(B[0]) == float or type(B[0]) == int
        assert type(B[1]) == float or type(B[1]) == int
        assert az >= A[0]
        assert az <= B[0]
        assert az < 90

        x1 = A[0]
        y1 = A[1]
        x2 = B[0]
        y2 = B[1]

        if x2 == x1:  # Vertical Line
            el = max(y1, y2)
        else:
            m = ((y2 - y1) / (x2 - x1))
            b = y1 - m * x1
            el = m * az + b

        assert el < 90

        return el

    def determine_el(self, az):
        """
        # Determine if the target altitude is above or below the determined minimum elevation for that azimuth

        Args:
            az (float or int): the target azimuth
        """

        el = 0
        prior_point = self.obstruction_points[0]
        i = 1
        found = False
        while(i < len(self.obstruction_points) and found is False):
            next_point = self.obstruction_points[i]
            if az >= prior_point[0] and az <= next_point[0]:
                el = self.interpolate(prior_point, next_point, az)
                found = True
            else:
                i += 1
                prior_point = next_point
        return el

    def get_score(self, time, observer, observation, **kwargs):

        target = observation.field
        veto = False
        score = self._score

        az = observer.altaz(time, target=target).az
        alt = observer.altaz(time, target=target).alt

        el = self.determine_el(az)

        # Determine if the target altitude is above or below the determined minimum elevation for that azimuth
        if alt - 7.5 > el:
            veto = True
        else:
            score = 100
        return veto, score * self.weight

        def __str__(self):
            return "Horizon {}".format(self.minimum)
