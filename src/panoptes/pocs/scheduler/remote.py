import httpx

from panoptes.pocs.scheduler.scheduler import BaseScheduler


class Scheduler(BaseScheduler):
    """A proxy Scheduler class that delegates scheduling decisions to a remote FastAPI service."""

    def __init__(
        self,
        observer,
        fields_list=None,
        fields_file=None,
        constraints=None,
        endpoint_url="http://localhost:8003",
        *args,
        **kwargs,
    ):
        # Initialize remote-specific attributes first because super().__init__ calls
        # methods that might use the remote API (e.g. clear_available_observations).
        self.endpoint_url = endpoint_url
        self.client = httpx.Client(timeout=30.0)
        super().__init__(
            observer,
            fields_list=fields_list,
            fields_file=fields_file,
            constraints=constraints,
            *args,
            **kwargs,
        )
        self.logger.info(f"Initialized RemoteScheduler pointing to {self.endpoint_url}")

    def _get(self, path, params=None):
        try:
            response = self.client.get(f"{self.endpoint_url}/{path}", params=params)
            response.raise_for_status()
            if "result" in response.json():
                return response.json()["result"]
            return response.json()
        except Exception as e:
            self.logger.error(f"Remote scheduler GET {path} failed: {e}")
            return None

    def _post(self, path, json=None, params=None):
        try:
            response = self.client.post(f"{self.endpoint_url}/{path}", json=json, params=params)
            response.raise_for_status()
            return response.json().get("result", True)
        except Exception as e:
            self.logger.error(f"Remote scheduler POST {path} failed: {e}")
            return None

    @property
    def status(self):
        status_dict = self._get("status")
        return status_dict or super().status

    @property
    def has_valid_observations(self) -> bool:
        """Whether there are any valid observations, delegating to the remote scheduler when possible."""
        result = self._get("has_valid_observations")
        if result is None:
            return super().has_valid_observations
        return bool(result)

    def get_observation(self, *args, **kwargs):
        """Ask the remote scheduler for the next observation.

        We pass the current time (if any) to the remote so it can evaluate constraints.
        The remote scheduler returns the name of the selected observation.
        We then return our local Observation object so POCS state tracking works.
        """
        params = {}
        if "time" in kwargs and kwargs["time"] is not None:
            params["time"] = kwargs["time"].isot

        obs_name = self._get("get_observation", params=params)

        if obs_name and obs_name in self.observations:
            obs = self.observations[obs_name]
            self.current_observation = obs
            return obs

        return None

    def clear_available_observations(self):
        """Clear available observations on both remote and local schedulers."""
        result = self._post("clear_available_observations")
        if not result:
            self.logger.error("Failed to clear available observations on remote scheduler")
            raise RuntimeError("Remote scheduler clear_available_observations failed")
        super().clear_available_observations()

    def reset_observed_list(self):
        """Reset the observed list on both remote and local schedulers."""
        result = self._post("reset_observed_list")
        if not result:
            self.logger.error("Failed to reset observed list on remote scheduler")
            raise RuntimeError("Remote scheduler reset_observed_list failed")
        super().reset_observed_list()

    def add_observation(self, observation_config: dict, **kwargs):
        """Add an observation to both remote and local schedulers."""
        result = self._post("add_observation", json={"observation_config": observation_config})
        if not result:
            self.logger.error("Failed to add observation on remote scheduler")
            raise RuntimeError("Remote scheduler add_observation failed")
        super().add_observation(observation_config, **kwargs)

    def remove_observation(self, field_name):
        """Remove an observation from both remote and local schedulers."""
        result = self._post("remove_observation", params={"field_name": field_name})
        if not result:
            self.logger.error("Failed to remove observation on remote scheduler")
            raise RuntimeError("Remote scheduler remove_observation failed")
        super().remove_observation(field_name)
