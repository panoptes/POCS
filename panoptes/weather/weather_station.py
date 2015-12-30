import os

from datetime import datetime as dt

from ..utils.database import PanMongo
from ..utils.logger import get_logger


class WeatherStation(object):

    """ The PANOPTES unit weather station

    This mostly provides convenience methods for querying the weather condition. The
    actual weather sensors run as a separate process from the PANOPTES unit.

    """

    def __init__(self, *args, **kwargs):

        self.logger = get_logger(self)
        self._is_safe = False
        self._translator = {True: 'safe', False: 'unsafe'}
        self.sensors = None

    def is_safe(self):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        """
        return self._is_safe

    def check_conditions(self, stale=180):
        """ Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Note:
            `stale` not implemented in the base class.

        Returns:
            str:       String describing state::

                { True: 'safe', False: 'unsafe' }

        """

        return self._translator.get(self.is_safe(), 'unsafe')

    def update_weather(self, update_mongo=True):
        '''
        '''
        data = {}
        data['Device Name'] = self.name
        data['Firmware Version'] = self.firmware_version
        data['Device Serial Number'] = self.serial_number
        if self.get_sky_temperature():
            data['Sky Temperature (C)'] = self.sky_temp.value
        if self.get_ambient_temperature():
            data['Ambient Temperature (C)'] = self.ambient_temp.value
        self.get_values()
        if self.internal_voltage:
            data['Internal Voltage (V)'] = self.internal_voltage.value
        if self.LDR_resistance:
            data['LDR Resistance (ohm)'] = self.LDR_resistance.value
        if self.rain_sensor_temp:
            data['Rain Sensor Temp (C)'] = self.rain_sensor_temp.value
        if self.get_rain_frequency():
            data['Rain Frequency'] = self.rain_frequency
        if self.get_PWM():
            data['PWM Value'] = self.PWM
        if self.get_errors():
            data['Errors'] = self.errors
#         if self.get_switch():
#             data['Switch Status'] = self.switch
        if self.get_wind_speed():
            data['Wind Speed (km/h)'] = self.wind_speed.value
        # Make Safety Decision
        self.safe_dict = make_safety_decision(self.cfg)
        data['Safe'] = self.safe_dict['Safe']
        data['Sky Safe'] = self.safe_dict['Sky']
        data['Wind Safe'] = self.safe_dict['Wind']
        data['Gust Safe'] = self.safe_dict['Gust']
        data['Rain Safe'] = self.safe_dict['Rain']

        if update_mongo:
            try:
                # Connect to sensors collection
                sensors = PanMongo().sensors
                if self.logger:
                    self.logger.info('Connected to mongo')
                sensors.insert({
                    "date": dt.utcnow(),
                    "type": "weather",
                    "data": data
                })
                if self.logger:
                    self.logger.info('  Inserted mongo document')
                sensors.update({"status": "current", "type": "weather"},
                               {"$set": {
                                   "date": dt.utcnow(),
                                   "type": "weather",
                                   "data": data,
                               }},
                               True)
                if self.logger:
                    self.logger.info('  Updated current status document')
            except:
                if self.logger:
                    self.logger.warning('Failed to update mongo database')
        else:
            print('{:>26s}: {}'.format('Date and Time',
                                       dt.utcnow().strftime('%Y/%m/%d %H:%M:%S')))
            for key in ['Ambient Temperature (C)', 'Sky Temperature (C)',
                        'PWM Value', 'Rain Frequency', 'Safe']:
                if key in data.keys():
                    print('{:>26s}: {}'.format(key, data[key]))
                else:
                    print('{:>26s}: {}'.format(key, 'no data'))
            print('')

        return self.safe


class WeatherStationMongo(WeatherStation):

    """
    This object is used to determine the weather safe/unsafe condition.

    Queries a mongodb collection for most recent values.
    """

    def __init__(self, *args, **kwargs):
        ''' Initialize the weather station with a mongodb connection. '''
        super().__init__(*args, **kwargs)

        self.logger.debug("Getting weather station connection to mongodb")
        self._db = PanMongo()
        self._sensors = self._db.sensors
        self.logger.debug("Weather station connection: {}".format(self._sensors))

    def is_safe(self, stale=180):
        ''' Determines whether current conditions are safe or not

        Args:
            stale(int): If reading is older than `stale` seconds, return False. Default 180 (seconds).

        Returns:
            bool:       Conditions are safe (True) or unsafe (False)
        '''
        # assert self.sensors is not None, self.logger.warning("No connection to sensors.")
        is_safe = super().__init__()

        now = dt.utcnow()
        try:
            is_safe = self._sensors.find_one({'type': 'weather', 'status': 'current'})['data']['Safe']
            self.logger.debug("is_safe: {}".format(is_safe))

            timestamp = self._sensors.find_one({'type': 'weather', 'status': 'current'})['date']
            self.logger.debug("timestamp: {}".format(timestamp))

            age = (now - timestamp).total_seconds()
            self.logger.debug("age: {}".format(age))
        except:
            self.logger.warning("Weather not safe or no record found in Mongo DB")
            is_safe = False
        else:
            if age > stale:
                is_safe = False

        self._is_safe = is_safe
        return self._is_safe


class WeatherStationSimulator(WeatherStation):

    """
    This object simulates safe/unsafe conditions.

    Args:
        simulator(path):    Set this to a file path to manually control safe/unsafe conditions.
            If the file exists, the weather is unsafe.  If the file does not exist, then conditions
            are safe.

    Returns:

    """

    def __init__(self, *args, **kwargs):
        ''' Simulator initializer  '''
        super().__init__(*args, **kwargs)

        if kwargs.get('simulator', None) is not None:
            if os.path.exists(simulator):
                self._is_safe = False
            else:
                self._is_safe = True

    def set_safe(self):
        """ Sets the simulator to safe weather """
        self._is_safe = True

    def set_unsafe(self):
        """ Sets the simulator to unsafe weather """
        self._is_safe = False

    def is_safe(self, stale=180):
        ''' Simulator simply returns the `self._is_safe` param '''
        return self._is_safe


if __name__ == '__main__':
    weather = WeatherStationMongo()
    safe = weather.check_conditions()
    translator = {True: 'safe', False: 'unsafe'}
    print('Conditions are {}'.format(translator[safe]))
