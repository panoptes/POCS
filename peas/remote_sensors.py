import requests
import logging

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils.database import PanDB
from pocs.utils.logger import get_root_logger
from pocs.utils.messaging import PanMessaging
from pocs.utils.config import load_config


class RemoteMonitor(object):
    """Does a pull request on an endpoint to obtain a JSON document."""

    def __init__(self, endpoint_url=None, sensor_name=None, *args, **kwargs):
        self.logger = get_root_logger()
        self.logger.setLevel(logging.INFO)

        self.config = load_config()

        # Setup the DB either from kwargs or config.
        self.db = None
        db_type = self.config.get('db.type', 'file')
        if 'db_type' in kwargs:
            self.logger.info(f"Setting up {kwargs['db_type']} type database")
            db_type = kwargs.get('db_type', db_type)

        self.db = PanDB(db_type=db_type)

        self.messaging = None

        self.sensor_name = sensor_name
        self.sensor = None

        if endpoint_url is None:
            # Get the config for the sensor
            endpoint_url = self.config.get(f'environment.{sensor_name}.url', None)
            if endpoint_url is None:
                raise error.PanError(f'No endpoint_url for {sensor_name}')

        if not endpoint_url.startswith('http'):
            endpoint_url = f'http://{endpoint_url}'

        self.endpoint_url = endpoint_url

    def disconnect(self):
        self.logger.debug('Stop listening on {self.endpoint_url}')

    def send_message(self, msg, topic='environment'):
        if self.messaging is None:
            msg_port = self.config.get('messaging.msg_port')
            try:
                self.messaging = PanMessaging.create_publisher(msg_port)
            except Exception as e:
                self.logger.warning(f"Can't send sensor message: {e!r}")
                return

        self.messaging.send_message(topic, msg)

    def capture(self, store_result=True, send_message=True):
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
        if send_message:
            self.send_message({'data': sensor_data}, topic='environment')

        if store_result and len(sensor_data) > 0:
            self.db.insert_current(self.sensor_name, sensor_data)

            # Make a separate power entry
            if 'power' in sensor_data:
                self.db.insert_current('power', sensor_data['power'])

        self.logger.debug(f'Remote data: {sensor_data}')
        return sensor_data
