import requests

from panoptes.utils import current_time
from panoptes.utils import error
from panoptes.utils.config.client import get_config
from panoptes.utils.database import PanDB
from panoptes.pocs.utils.logger import get_logger


class RemoteMonitor(object):
    """Does a pull request on an endpoint to obtain a JSON document."""

    def __init__(self, endpoint_url=None, sensor_name=None, *args, **kwargs):
        self.logger = get_logger()
        self.logger.info(f'Setting up remote sensor {sensor_name}')

        # Setup the DB either from kwargs or config.
        self.db = None
        db_type = get_config('db.type', default='file')

        if 'db_type' in kwargs:
            self.logger.info(f"Setting up {kwargs['db_type']} type database")
            db_type = kwargs.get('db_type', db_type)

        self.db = PanDB(db_type=db_type)

        self.sensor_name = sensor_name
        self.sensor = None

        if endpoint_url is None:
            # Get the config for the sensor
            endpoint_url = get_config(f'environment.{sensor_name}.url')
            if endpoint_url is None:
                raise error.PanError(f'No endpoint_url for {sensor_name}')

        if not endpoint_url.startswith('http'):
            endpoint_url = f'http://{endpoint_url}'

        self.endpoint_url = endpoint_url

    def disconnect(self):
        self.logger.debug('Stop listening on {self.endpoint_url}')

    def capture(self, store_result=True):
        """Read JSON from endpoint url and capture data.

        Note:
            Currently this doesn't do any processing or have a callback.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        self.logger.debug(f'Capturing data from remote url: {self.endpoint_url}')
        sensor_data = requests.get(self.endpoint_url).json()
        if isinstance(sensor_data, list):
            sensor_data = sensor_data[0]

        self.logger.debug(f'Captured on {self.sensor_name}: {sensor_data!r}')

        sensor_data['date'] = current_time(flatten=True)

        if store_result and len(sensor_data) > 0:
            self.db.insert_current(self.sensor_name, sensor_data)

            # Make a separate power entry
            if 'power' in sensor_data:
                self.db.insert_current('power', sensor_data['power'])

        self.logger.debug(f'Remote data: {sensor_data}')
        return sensor_data
