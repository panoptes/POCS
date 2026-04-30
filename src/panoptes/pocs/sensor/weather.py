"""AAG CloudWatcher weather station integration for PANOPTES."""

from aag.weather import CloudSensor

from panoptes.pocs.base import PanBase


class WeatherStation(PanBase):
    """POCS weather station.

    A thin wrapper with support for putting entries into the database.
    """

    def __init__(
        self,
        serial_port: str = None,
        name: str = "Weather Station",
        db_collection: str = "weather",
        *args,
        **kwargs,
    ):
        """Initialize the weather station.

        Args:
            serial_port (str, optional): The dev port for the mount, usually the usb-serial converter.
            name (str): The user-friendly name for the weather station.
            db_collection (str): Which collection (i.e. table) to store the values in, default 'weather'.
        """
        super().__init__(*args, **kwargs)

        conf = self.get_config("environment.weather", {})

        # Update with passed parameters.
        conf.update(kwargs)
        conf.pop("auto_detect", None)

        # Remove the conf port if passed one.
        if serial_port is not None:
            conf.pop("serial_port", None)

        self.serial_port = serial_port or conf.get("serial_port", "/dev/ttyUSB0")
        self.name = name
        self.collection_name = db_collection
        self.store_permanently = conf.pop("store_permanently", False)

        self.logger.debug(f"Setting up weather station connection for {name=} on {self.serial_port}")
        self.weather_station = CloudSensor(serial_port=self.serial_port, **conf)

        self.logger.debug(f"Weather station config: {self.weather_station.config}")
        self.logger.info(f"{self.weather_station} initialized")

    @property
    def status(self):
        """Returns the most recent weather reading.

        Returns:
            dict | str: A dictionary of the most recent sensor values, or a string
                message if no readings are available yet. The dictionary contains the
                following fields:

                - **timestamp** (*str*): ISO 8601 datetime of the reading
                  (e.g. ``"2024-01-15T10:30:00.123456"``).
                - **ambient_temp** (*float*): Ambient temperature in degrees Celsius.
                - **sky_temp** (*float*): Sky (infrared) temperature in degrees Celsius.
                  Subtract ``ambient_temp`` to get the cloud-temperature delta.
                - **wind_speed** (*float*): Wind speed in m/s.
                - **rain_frequency** (*float*): Raw rain-sensor frequency value.
                  Higher values indicate drier conditions.
                - **pwm** (*float*): Heater duty cycle in percent.
                - **cloud_condition** (*str*): One of ``"clear"``, ``"cloudy"``,
                  ``"very cloudy"``, or ``"unknown"``.
                - **wind_condition** (*str*): One of ``"calm"``, ``"windy"``,
                  ``"very windy"``, ``"gusty"``, ``"very gusty"``, or ``"unknown"``.
                - **rain_condition** (*str*): One of ``"dry"``, ``"wet"``, ``"rainy"``,
                  or ``"unknown"``.
                - **cloud_safe** (*bool*): ``True`` when ``cloud_condition == "clear"``.
                - **wind_safe** (*bool*): ``True`` when ``wind_condition == "calm"``.
                - **rain_safe** (*bool*): ``True`` when ``rain_condition == "dry"``.
                - **is_safe** (*bool*): ``True`` only when *all three* of
                  ``cloud_safe``, ``wind_safe``, and ``rain_safe`` are ``True``.
        """
        reading = "No valid readings found. If the system just started, wait a few seconds and try again."
        try:
            reading = self.weather_station.readings[-1]
        except Exception as e:
            self.logger.warning(f"Could not get reading: {e!r}")

        return reading

    def record(self):
        """Capture a fresh reading and persist it to the database.

        Calls :meth:`aag.weather.CloudSensor.get_reading` to obtain an averaged
        sensor snapshot, then stores it in the ``weather`` database collection via
        :meth:`panoptes.utils.db.PanDB.insert_current`.

        The stored document contains the same fields described in :attr:`status`.
        The two fields that POCS reads back when evaluating safety are:

        - **is_safe** (*bool*): Overall safety flag — ``True`` only when cloud,
          wind, and rain conditions are all individually safe.
        - **timestamp** (*str*): ISO 8601 datetime used to determine whether the
          record is stale (default staleness threshold: 180 s).

        Returns:
            dict: The reading dictionary that was written to the database.
        """
        recent_values = self.weather_station.get_reading()

        self.db.insert_current(self.collection_name, recent_values, store_permanently=self.store_permanently)

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
        return f"{self.name} {self.weather_station}"
