from pocs.focuser.focuser import AbstractFocuser
from pocs.utils.rs232 import SerialData

class Focuser(AbstractFocuser):
    """
    Focuser class for control of a Canon DSLR lens via a Birger Engineering Canon EF-232 adapter
    """
    def __init__(self,
                 name='Birger Focuser',
                 model='Canon EF-232',
                 *args, **kwargs):
        super().__init__(*args, name=name, model=model, **kwargs)
        self.logger.debug('Initialising Birger focuser')
        self._serial = SerialData(port=self.port, baudrate=115200, threaded=False, name='Birger')
        self.connect()
        

##################################################################################################
# Public Methods
##################################################################################################

    def connect(self):
        if not self._serial.connect():
            self.logger.error('Could not connect to {}!'.format(self))
            return

        self._connected = True
        

    def move_to(self, position):
        pass

    def move_by(self, position):
        pass

##################################################################################################
# Private Methods
##################################################################################################

    def _send_command(self, command):
        if not self._connected:
            self.logger.error("{} not connected, cannot send command '{}'!".format(self, command))
            return

        self._serial.write(command + '\r')
        response = self._serial.read().split()
        if response[0] != command:
            self.logger.error("Sent command '{}', Birger echoed '{}'!".format(command, response[0]))
        if response[1] != 'OK':
            try:
                error_number = int(response[1][3:])
                message = error_messages[error_number]
                self.logger.error("Sent command '{}', got error message '{}'!".format(command, message))
            except IndexError:
                self.logger.error("Sent command '{}', got unrecognised error message '{}'!".format(command,
                                                                                                   response[1]))
        if len(response) > 2:
            return response[2:]
        else:
            return


error_messages = ('No error',
                  'Unrecognised command',
                  'Lens is in manual focus mode',
                  'No lens connected',
                  'Lens distance stop error',
                  'Aperture not initialised',
                  'Invalid baud rate specified',
                  'Reserved',
                  'Reserved',
                  'A bad parameter was supplied to the command',
                  'XModem timeout',
                  'XModem error',
                  'XModem unlock code incorrect',
                  'Not used',
                  'Invalid port',
                  'Licence unlock failure',
                  'Invalid licence file',
                  'Invalid library file',
                  'Reserved',
                  'Reserved',
                  'Not used',
                  'Library not ready for lens communications',
                  'Library not ready for commands',
                  'Command not licensed',
                  'Invalid focus range in memory. Try relearning the range',
                  'Distance stops not supported by the lens')                                  
