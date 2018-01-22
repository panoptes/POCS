from astropy import units as u

from astropy.coordinates import get_moon

from pocs.utils import current_time
from pocs.utils import listify
from pocs.scheduler import BaseScheduler


class Scheduler(BaseScheduler):

    def __init__(self, *args, **kwargs):
        """ Inherit from the `BaseScheduler` """
        BaseScheduler.__init__(self, *args, **kwargs)


##########################################################################
# Properties
##########################################################################

##########################################################################
# Methods
##########################################################################

    def get_observation(self, time=None, show_all=False):
        """Get a valid observation

        Args:
            time (astropy.time.Time, optional): Time at which scheduler applies,
                defaults to time called
            show_all (bool, optional): Return all valid observations along with
                merit value, defaults to False to only get top value

        Returns:
            tuple or list: A tuple (or list of tuples) with name and score of ranked observations
        """

        if time is None:
            time = current_time()

        valid_obs = {obs: 1.0 for obs in self.observations}
        best_obs = []

        common_properties = {
            'end_of_night': self.observer.tonight(time=time, horizon=-18 * u.degree)[-1],
            'moon': get_moon(time, self.observer.location),
            'observed_list': self.observed_list
        }

        for constraint in listify(self.constraints):
            self.logger.info("Checking Constraint: {}".format(constraint))
            for obs_name, observation in self.observations.items():
                if obs_name in valid_obs:
                    self.logger.debug("\tObservation: {}".format(obs_name))

                    veto, score = constraint.get_score(
                        time, self.observer, observation, **common_properties)

                    self.logger.debug("\t\tScore: {:.05f}\tVeto: {}".format(score, veto))

                    if veto:
                        self.logger.debug("\t\t{} vetoed by {}".format(obs_name, constraint))
                        del valid_obs[obs_name]
                        continue

                    valid_obs[obs_name] += score

        for obs_name, score in valid_obs.items():
            valid_obs[obs_name] += self.observations[obs_name].priority

        if len(valid_obs) > 0:
            # Sort the list by highest score (reverse puts in correct order)
            best_obs = sorted(valid_obs.items(), key=lambda x: x[1])[::-1]

            top_obs = best_obs[0]

            # Check new best against current_observation
            if self.current_observation is not None \
                    and top_obs[0] != self.current_observation.name:

                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if self.observation_available(self.current_observation, end_of_next_set):

                    # If current is better or equal to top, use it
                    if self.current_observation.merit >= top_obs[1]:
                        best_obs.insert(0, self.current_observation)

            # Set the current
            self.current_observation = self.observations[top_obs[0]]
            self.current_observation.merit = top_obs[1]
        else:
            if self.current_observation is not None:
                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if end_of_next_set < common_properties['end_of_night'] and \
                        self.observation_available(self.current_observation, end_of_next_set):

                    self.logger.debug("Reusing {}".format(self.current_observation))
                    best_obs = [(self.current_observation.name, self.current_observation.merit)]
                else:
                    self.logger.warning("No valid observations found")
                    self.current_observation = None

        if not show_all and len(best_obs) > 0:
            best_obs = best_obs[0]

        return best_obs


##########################################################################
# Utility Methods
##########################################################################

##########################################################################
# Private Methods
##########################################################################
