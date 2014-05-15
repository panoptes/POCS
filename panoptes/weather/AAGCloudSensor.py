import datetime

import panoptes.utils.logger as logger
import serial
import panoptes.weather.WeatherStation as WeatherStation


@logger.has_logger
class AAGCloudSensor(WeatherStation.WeatherStation):
    def __init__(self, serial_address='/dev/ttyS0'):
        super().__init__()
        self.logger.debug('Using serial address: {}'.format(serial_address))
        self.logger.info('Connecting to AAG Cloud Sensor')
        try:
            self.AAG = serial.Serial(serial_address, 9600, timeout=2)
            self.logger.info("Connected to Cloud Sensor on {}".format(serial_address))
        except:
            self.logger.error("Unable to connect to AAG Cloud Sensor")
            self.AAG = None


    def query(self, send, nResponses):
        if AAG:
            nBytes = nResponses*15
            ## Clear Response Buffer
            while self.AAG.inWaiting() > 0:
                self.logger.debug('Clearing Buffer: {0}'.format(self.AAG.read(1)))
            ## Send Query to Device
            self.AAG.write(send)
            ## read Response
            self.logger.debug("Attempting to read response.")
            responseString = self.AAG.read((nResponses+1)*15)
            ## Check for Hand Shaking Block
            HSBgood = re.match('!'+chr(17)+'\s{12}0', responseString[-15:])
            if not HSBgood:
                self.logger.debug("Handshaking Block Bad")
            ## Check that Response Matches Standard Pattern
            ResponsePattern = '(\![\s\w]{2})([\s\w]{12})'*nResponses
            ResponseMatch = re.match(ResponsePattern, responseString[0:-15])
            if not ResponseMatch:
                self.logger.debug("Response does not match expected pattern: {}".format(responseString[0:-15]))
            if HSBgood and ResponseMatch:
                ResponseArray = []
                for i in range(0,nResponses):
                    ResponseArray.append([ResponseMatch.group(1), ResponseMatch.group(2)])
                return ResponseArray
            else:
                return None
        else:
            self.logger.warning('Not conencted to AAG Cloud Sensor')
            return None


    def get_ambient_temperature(self):
        send = "!T"
        flag = "!2 "
        response = self.query(send, 1)
        if response:
            logger.debug('Response Recieved: {}{}'.format(response[0][0], response[0][1]))
            if response[0][0] == flag:
                AmbTempC = float(response[0][1])/100.
                AmbTempF = AmbTempC*1.8+32.
                logger.info('Ambient Tmperature is {:.1f} deg F'.format(AmbTempF))
                logger.info('Ambient Tmperature is {:.1f} deg C'.format(AmbTempC))
        else:
            logger.warning("No response recieved.")


    def get_sky_temperature(self):
        send = "!S"
        flag = "!1 "
        response = self.query(send, 1)
        if response:
            logger.debug('Response Recieved: {}{}'.format(response[0][0], response[0][1]))
            if response[0][0] == flag:
                SkyTempC = float(response[0][1])/100.
                SkyTempF = SkyTempC*1.8+32.
                logger.info('Ambient Tmperature is {:.1f} deg F'.format(SkyTempF))
                logger.info('Ambient Tmperature is {:.1f} deg C'.format(SkyTempC))
        else:
            logger.warning("No response recieved.")


if __name__ == '__main__':
    test = AAGCloudSensor()
    print(test.telemetry_file)
    
