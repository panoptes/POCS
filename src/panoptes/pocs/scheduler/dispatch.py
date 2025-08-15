from panoptes.pocs.scheduler.scheduler import BaseScheduler
from panoptes.utils.time import current_time
from panoptes.utils.utils import listify


class Scheduler(BaseScheduler):
    def __init__(self, *args, **kwargs):
        """Inherit from the `BaseScheduler`"""
        BaseScheduler.__init__(self, *args, **kwargs)

    def get_observation(self, time=None, show_all=False, constraints=None, read_file=False):
        """Get a valid observation.

        Args:
            time (astropy.time.Time, optional): Time at which scheduler applies,
                defaults to time called
            constraints (list of panoptes.pocs.scheduler.constraint.Constraint, optional): The
                constraints to check. If `None` (the default), use the `scheduler.constraints`.
            show_all (bool, optional): Return all valid observations along with
                merit value, defaults to False to only get top value
            constraints (list of panoptes.pocs.scheduler.constraint.Constraint, optional): The
                constraints to check. If `None` (the default), use the `scheduler.constraints`
            read_file (bool, optional): If the fields file should be reread
                before scheduling occurs, defaults to False.

        Returns:
            tuple or list: A tuple (or list of tuples) with name and score of ranked observations
        """
        if read_file:
            self.logger.debug("Rereading fields file")
            self.read_field_list()

        if time is None:
            time = current_time()

        valid_obs = {obs: 0.0 for obs in self.observations}
        best_obs = []

        self.set_common_properties(time)

        self.logger.info("Applying constraints to observations:")
        for obs_name, observation in self.observations.items():
            self.logger.info(f"{obs_name}")
            # Get the global constraints.
            all_constraints = constraints or self.constraints.copy()

            # Add the observation specific constraints.
            if observation.constraints is not None:
                all_constraints += observation.constraints

            for constraint in listify(all_constraints):
                if obs_name in valid_obs:
                    # Add a special case where we skip the Moon Avoidance constraint if the observation name is "Moon".
                    if constraint.name == "MoonAvoidance" and obs_name.lower() == "moon":
                        self.logger.info(f"Skipping Moon Avoidance constraint for {obs_name}")
                        continue

                    veto, score = constraint.get_score(
                        time, self.observer, observation, **self.common_properties
                    )

                    if veto:
                        self.logger.info(f"\tVetoed by {constraint}")
                        del valid_obs[obs_name]
                        continue

                    valid_obs[obs_name] += score
                    self.logger.info(
                        f"\t{str(constraint):30s}Constraint score: {score:10.02f}\tTotal score: {valid_obs[obs_name]:10.02f}"
                    )

        if len(valid_obs) > 0:
            self.logger.info(f"Multiplying final scores by observation priority")
            for obs_name, score in valid_obs.items():
                priority = self.observations[obs_name].priority
                new_score = score * priority
                self.logger.info(
                    f"\t{obs_name:30s}Total score:      {score:10.02f}\tPriority:    {priority:10.3f} = {new_score:10.02f}"
                )
                valid_obs[obs_name] = new_score

            # Sort the list by highest score (reverse puts in correct order)
            best_obs = sorted(valid_obs.items(), key=lambda x: x[1])[::-1]

            top_obs_name, top_obs_score = best_obs[0]
            self.logger.info(f"Best observation: {top_obs_name}\tScore: {top_obs_score:.02f}")

            # Check new best against current_observation
            if (
                self.current_observation is not None
                and top_obs_name != self.current_observation.name
            ):
                self.logger.info(f"Checking if {self.current_observation} is still valid")

                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if self.observation_available(self.current_observation, end_of_next_set):
                    # If current is better or equal to top, use it
                    self.logger.debug(f"{self.current_observation.merit=}")
                    self.logger.debug(f"{top_obs_score=}")
                    if self.current_observation.merit >= top_obs_score:
                        best_obs.insert(
                            0, (self.current_observation, self.current_observation.merit)
                        )

            # Set the current
            self.current_observation = self.observations[top_obs_name]
            self.current_observation.merit = top_obs_score
        else:
            if self.current_observation is not None:
                # Favor the current observation if still available
                end_of_next_set = time + self.current_observation.set_duration
                if end_of_next_set < self.common_properties[
                    "end_of_night"
                ] and self.observation_available(self.current_observation, end_of_next_set):
                    self.logger.info(f"Reusing {self.current_observation}")
                    best_obs = [(self.current_observation.name, self.current_observation.merit)]
                else:
                    self.logger.warning("No valid observations found")
                    self.current_observation = None

        if not show_all and len(best_obs) > 0:
            best_obs = best_obs[0]

        return best_obs
