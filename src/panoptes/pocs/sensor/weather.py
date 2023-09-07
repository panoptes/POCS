from aag.weather import CloudSensor

from panoptes.pocs.base import PanBase


class WeatherStation(PanBase):
    """POCS weather station.

    A thin wrapper with support for putting entries into the database.
    """

    def __init__(self,
                 port: str = None,
                 name: str = 'Weather Station',
                 db_collection: str = 'weather',
                 *args, **kwargs):
        """Initialize the weather station.

        Args:
            port (str, optional): The dev port for the mount, usually the usb-serial converter.
            name (str): The user-friendly name for the weather station.
            db_collection (str): Which collection (i.e. table) to store the values in, default 'weather'.
        """
        super().__init__(*args, **kwargs)

        self.port = port or self.get_config('environment.weather.port', '/dev/ttyUSB0')
        self.name = name
        self.collection_name = db_collection

        self.logger.debug(f'Setting up weather station connection for {name=} on {self.port}')
        self.weather_station = CloudSensor(serial_port=self.port)

        self.logger.info(f'{self.weather_station} initialized')

    @property
    def status(self):
        """Returns the most recent weather reading."""
        return self.weather_station.readings[-1]

    def record(self):
        """Record the rolling mean of the power readings in the database."""
        recent_values = self.weather_station.get_reading()

        self.db.insert_current(self.collection_name, recent_values)

        return recent_values

    def readings(self, num_readings: int = 20):
        """Returns weather readings.

        Args:
            num_readings (int, optional): The number of readings to return, default
                20. Note that the weather station itself might be configured to
                store less than this.
        """
        return self.weather_station.readings[-num_readings:]

    def __str__(self):
        return f'{self.name} {self.weather_station}'
