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
        super().__init__(
            observer,
            fields_list=fields_list,
            fields_file=fields_file,
            constraints=constraints,
            *args,
            **kwargs,
        )
        self.endpoint_url = endpoint_url
        self.client = httpx.Client(timeout=30.0)
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

    def has_valid_observations(self):
        return self._get("has_valid_observations")

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
        super().clear_available_observations()
        self._post("clear_available_observations")

    def reset_observed_list(self):
        super().reset_observed_list()
        self._post("reset_observed_list")

    def add_observation(self, observation_config: dict, **kwargs):
        super().add_observation(observation_config, **kwargs)
        self._post("add_observation", json={"observation_config": observation_config})

    def remove_observation(self, field_name):
        super().remove_observation(field_name)
        self._post("remove_observation", params={"field_name": field_name})
