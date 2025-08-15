import requests
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.time import current_time

from panoptes.pocs.base import PanBase


class RemoteMonitor(PanBase):
    """Does a pull request on an endpoint to obtain a JSON document."""

    def __init__(self, endpoint_url: str = None, sensor_name: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.info(f"Setting up remote sensor {sensor_name}")

        self.sensor_name = sensor_name
        self.sensor = None

        if endpoint_url is None:
            # Get the config for the sensor
            endpoint_url = get_config(f"environment.{sensor_name}.url")
            if endpoint_url is None:
                raise error.PanError(f"No endpoint_url for {sensor_name}")

        if not endpoint_url.startswith("http"):
            endpoint_url = f"http://{endpoint_url}"

        self.endpoint_url = endpoint_url

    def disconnect(self):
        self.logger.debug("Stop listening on {self.endpoint_url}")

    def capture(self, store_result: bool = True) -> dict:
        """Read JSON from endpoint url and capture data.

        Note:
            Currently this doesn't do any processing or have a callback.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        self.logger.debug(f"Capturing data from remote url: {self.endpoint_url}")
        try:
            sensor_data = requests.get(self.endpoint_url).json()
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"No connection at {self.endpoint_url}")
            return {}
        if isinstance(sensor_data, list):
            sensor_data = sensor_data[0]

        self.logger.debug(f"Captured on {self.sensor_name}: {sensor_data!r}")

        sensor_data["date"] = current_time(flatten=True)

        if store_result and len(sensor_data) > 0:
            self.db.insert_current(self.sensor_name, sensor_data, store_permanently=False)

            # Make a separate power entry
            if "power" in sensor_data:
                self.db.insert_current("power", sensor_data["power"], store_permanently=False)

        self.logger.debug(f"Remote data: {sensor_data}")

        return sensor_data
