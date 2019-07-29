import requests
import logging

from panoptes.utils import current_time
from panoptes.utils.config.client import get_config
from panoptes.utils.database import PanDB
from panoptes.utils.logger import get_root_logger
from panoptes.serializers import from_json
from panoptes.utils.messaging import PanMessaging


class RemoteSerialMonitor(object):
    """Does a pull request on an endpoint to obtain a JSON document."""

    def __init__(self, endpoint_url=None, sensor_name=None, *args, **kwargs):
        self.logger = get_root_logger()
        self.logger.setLevel(logging.INFO)

        self.db = None
        if 'db_type' in kwargs:
            self.logger.info(f"Setting up {kwargs['db_type']} type database")
            self.db = PanDB(db_type=kwargs['db_type'])

        self.messaging = None

        self.sensor_name = sensor_name
        self.sensor = None

        if endpoint_url is None:
            # Get the config for the sensor
            endpoint_url = get_config(f'environment.{sensor_name}.url')

        self.endpoint_url = endpoint_url

    def disconnect(self):
        self.logger.debug('Stop listening on {self.endpoint_url}')

    def send_message(self, msg, topic='environment'):
        if self.messaging is None:
            msg_port = get_config('messaging.msg_port')
            self.messaging = PanMessaging.create_publisher(msg_port)

        self.messaging.send_message(topic, msg)

    def capture(self, store_result=True, send_message=True):
        """Read JSON from endpoint url and capture data.

        Note:
            Currently this doesn't do any processing or have a callback.

        Returns:
            sensor_data (dict):     Dictionary of sensors keyed by sensor name.
        """

        sensor_data = from_json(requests.get(self.endpoint_url))

        sensor_data['date'] = current_time(flatten=True)
        if send_message:
            self.send_message({'data': sensor_data}, topic='environment')

        if store_result and len(sensor_data) > 0:
            if self.db is None:
                self.db = PanDB()

            self.db.insert_current(self.sensor_name, sensor_data)

            # Make a separate power entry
            if 'power' in sensor_data:
                self.db.insert_current('power', sensor_data['power'])

        return sensor_data
