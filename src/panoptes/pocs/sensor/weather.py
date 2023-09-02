from typing import Optional, Callable

import pandas as pd
from aag.weather import CloudSensor
from astropy import units as u
from panoptes.utils.time import current_time
from streamz.dataframe import PeriodicDataFrame

from panoptes.pocs.base import PanBase


class WeatherStation(PanBase):
    """POCS weather station.

    Ideally just a thin wrapper.
    """

    def __init__(self,
                 port: str = None,
                 name: str = 'Weather Station',
                 reader_callback: Callable[[dict], dict] = None,
                 dataframe_period: int = 1,
                 mean_interval: Optional[int] = 5,
                 *args, **kwargs):
        """Initialize the weather station.

        Args:
            port (str, optional): The dev port for the arduino, if not provided, search for port
                matching the vendor (2341) and product id (0043).
            name (str): The user-friendly name for the power board.
            reader_callback (Callable): A callback for the serial readings. The
                default callback will update the pin values and record data in a
                json format, which is then made into a dataframe with the `to_dataframe`.
            dataframe_period (int): The period to use for creating the
                `PeriodicDataFrame`, default `2` (seconds).
            mean_interval (int): When taking a rolling mean, use this many seconds,
                default 5.
            arduino_board_name (str): The name of the arduino board to match in
                the callback and the collection name for storing in `record.
        """
        super().__init__(*args, **kwargs)

        self.port = port or self.get_config('environment.weather.port', '/dev/ttyUSB0')
        self.name = name

        self.logger.debug(f'Setting up weather station connection for {name=} on {self.port}')
        self._ignore_readings = 5
        self.weather_station = CloudSensor(serial_port=self.port)

        self.dataframe = None
        if dataframe_period is not None:
            self.dataframe = PeriodicDataFrame(interval=f'{dataframe_period}s',
                                               datafn=self.to_dataframe)

        self._mean_interval = mean_interval

        self.logger.info(f'{self.weather_station} initialized')

    @property
    def status(self):
        return self.readings

    @property
    def readings(self):
        """Return the rolling mean of the readings. """
        time_start = (current_time() - self._mean_interval * u.second).to_datetime()
        df = self.to_dataframe()[time_start:]
        values = df.mean().astype('int').to_dict()

        return values

    def to_dataframe(self, **kwargs):
        """Make a dataframe from the latest readings.

        This method is called by a `streamz.dataframe.PeriodicDataFrame`.

        """
        try:
            # columns = ['time', 'ac_ok'] + list(self.relay_labels.keys())
            # df0 = pd.DataFrame(self.weather_station.readings, columns=columns)
            df0 = pd.DataFrame(self.weather_station.readings)
            df0.set_index(['time'], inplace=True)
        except:
            df0 = pd.DataFrame([], index=pd.DatetimeIndex([]))

        return df0

    def record(self, collection_name: str = 'weather'):
        """Record the rolling mean of the power readings in the database.

        Args:
            collection_name (str): Where to store the results in the db. If None
                (the default), then use `arduino_board_name`.

        """
        recent_values = self.readings

        self.db.insert_current(collection_name, recent_values)

        return recent_values

    def __str__(self):
        return f'{self.name} {self.weather_station}'
