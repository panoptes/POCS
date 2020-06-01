from panoptes.utils import current_time
from panoptes.utils import listify
from panoptes.pocs.scheduler import BaseScheduler


class Scheduler(BaseScheduler):

    def __init__(self, *args, **kwargs):
        """ Inherit from the `BaseScheduler` """
        BaseScheduler.__init__(self, *args, **kwargs)

    def get_observation(self, time=None, show_all=False, reread_fields_file=False):
        """Get a valid observation

        Args:
            time (astropy.time.Time, optional): Time at which scheduler applies,
                defaults to time called
            show_all (bool, optional): Return all valid observations along with
                merit value, defaults to False to only get top value
            reread_fields_file (bool, optional): If the fields file should be reread
                before scheduling occurs, defaults to False.

        Returns:
            tuple or list: A tuple (or list of tuples) with name and score of ranked observations
        """
        if reread_fields_file:
            self.logger.debug("Rereading fields file")
            self.read_field_list()

        if time is None:
            time = current_time()

        valid_obs = {obs: 0.0 for obs in self.observations}
        best_obs = []

        self.set_common_properties(time)

        for constraint in listify(self.constraints):
            self.logger.info("Checking Constraint: {}".format(constraint))
            for obs_name, observation in self.observations.items():
                if obs_name in valid_obs:
                    current_score = valid_obs[obs_name]
                    self.logger.debug(f"\t{obs_name}\tCurrent score: {current_score:.03f}")

                    veto, score = constraint.get_score(time,
                                                       self.observer,
                                                       observation,
                                                       **self.common_properties)

                    self.logger.debug(f"\t\tConstraint Score: {score:.03f}\tVeto: {veto}")

                    if veto:
                        self.logger.debug(f"\t\tVetoed by {constraint}")
                        del valid_obs[obs_name]
                        continue

                    valid_obs[obs_name] += score
                    self.logger.debug(f"\t\tTotal score: {valid_obs[obs_name]:.03f}")

        self.logger.debug(f'Multiplying final scores by priority')
        for obs_name, score in valid_obs.items():
            priority = self.observations[obs_name].priority
            new_score = score * priority
            self.logger.debug(f'{obs_name}: {priority:7.2f} *{score:7.2f} = {new_score:7.2f}')
            valid_obs[obs_name] = new_score

        if len(valid_obs) > 0:
            # Sort the list by highest score (reverse puts in correct order)
            best_obs = sorted(valid_obs.items(), key=lambda x: x[1])[::-1]

            top_obs_name, top_obs_score = best_obs[0]
            self.logger.info(f'Best observation: {top_obs_name}\tScore: {top_obs_score:.02f}')

            # Check new best against current_observation
            if self.current_observation is not None \
                    and top_obs_name != self.current_observation.name:

                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if self.observation_available(self.current_observation, end_of_next_set):

                    # If current is better or equal to top, use it
                    if self.current_observation.merit >= top_obs_score:
                        best_obs.insert(0, (self.current_observation,
                                            self.current_observation.merit))

            # Set the current
            self.current_observation = self.observations[top_obs_name]
            self.current_observation.merit = top_obs_score
        else:
            if self.current_observation is not None:
                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if end_of_next_set < self.common_properties['end_of_night'] and \
                        self.observation_available(self.current_observation, end_of_next_set):

                    self.logger.debug("Reusing {}".format(self.current_observation))
                    best_obs = [(self.current_observation.name, self.current_observation.merit)]
                else:
                    self.logger.warning("No valid observations found")
                    self.current_observation = None

        if not show_all and len(best_obs) > 0:
            best_obs = best_obs[0]

        return best_obs
