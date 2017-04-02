from astropy import units as u

from .. import PanBase


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

        moon_sep = observation.field.coord.separation(moon).value

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

    #@obstruction_points = [] #How exactly do I use decorators to declare properties/do I need to use a decorator?
    def __init__(self, obstruction_points, *args, **kwargs):  # Constructor
        super().__init__(*args, **kwargs)  # Calls parent's (BaseConstraint's) constructor

        # assert the validation conditions

        self.obstruction_points = obstruction_points

    # Process the horizon_image to generate the obstruction_points list
    # Segment regions of high contrast using scikit image
    # Image Segmentation with Watershed Algorithm
    # def process_image():

    # Get the user to input az, el coordinates
    # After a horizon instant has been instantiated this method can be called
    # to populate the obstruction_points from user input

    def enter_coords():

        import ast

        valid = False
        while(valid == False):

            print("Enter a list of points. For example (0,0), (0,1), (1,1), (1,0)")

            points = input()

            try:
                if isinstance(points, tuple)
                    valid = True
                else
                    print(
                        "Input type error. Please enter the coordinates in the format mentioned")
            except SyntaxError:
                print(
                    "Syntax error. Please enter the coordinates in the format mentioned")

        return points

    def interpolate(A, B, az):

        # input validation assertions
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

        if B[0] == A[0]:
            el = B[1]
        else:
            m = ((B[1] - A[1]) / (B[0] - A[0]))
            # Same as y=mx+b
            el = m * az + A[1]

        assert el < 90

        return el

    # Search the base constraint for the adjacent pair of tuples that contains the target azimuth
    # Its possible that a single tuple will have a matching azimuth to the target azimuth - special case
    #Pass in (x1, y1), (x2, y2), target.az
    # Return elevation

    def determine_el(az):
        el = 0
        prior_point = obstruction_points[0]
        i = 1
        found = False
        while(i < len(obstruction_points) and found == False):
            next_point = obstruction_points[i]
            if az >= prior_point[0] and az <= next_point[0]:
                el = interpolate(prior_point, next_point, az)
                found = True
            else:
                i += 1
                prior_point = next_point
        return el

    # Determine if the target altitude is above or below the determined
    # minimum elevation for that azimuth - inside get_score

    def get_score(self, time, observer, observation, **kwargs):

        target = observation.field
        # Is this using the astropy units to declare the constraint?
        #"A decorator for validating the units of arguments to functions."
        veto = False
        score = self._score

        az = observer.altaz(time, target=target).az
        alt = observer.altaz(time, target=target).alt

        el = determine_el(az)

        # Determine if the target altitude is above or below the determined minimum elevation for that azimuth
        # Note the image is 10 by 15, so I want it to be 7.5 below the target's
        # elevation

        if alt - 7.5 > el
            veto = True
        else:
            score = 100

        # Once the equation is found put the target azimuth into the equation to determine the minimum altitude for that azimuth
        # assume everything has a default score of 100
        return veto, score * self.weight

        def __str__(self):
            return "Horizon {}".format(self.minimum)
