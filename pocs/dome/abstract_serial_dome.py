from pocs import dome
from pocs.utils import error
from pocs.utils import rs232


class AbstractSerialDome(dome.AbstractDome):
    """Abstract base class for controlling a dome via a serial connection.

    Takes care of a single thing: configuring the connection to the device.
    """

    def __init__(self, *args, **kwargs):
        """Initialize an AbstractSerialDome.

        Creates a serial connection to the port indicated in the config.
        """
        super().__init__(*args, **kwargs)

        # Get config info, e.g. which port (e.g. /dev/ttyUSB123) should we use?
        cfg = self._dome_config
        self._port = cfg.get('port')
        if not self._port:
            msg = 'No port specified in the config for dome: {}'.format(cfg)
            self.logger.error(msg)
            raise error.DomeNotFound(msg=msg)

        baudrate = int(cfg.get('baudrate', 9600))

        # Setup our serial connection to the given port.
        self.ser = None
        try:
            self.ser = rs232.SerialData(port=self._port, baudrate=baudrate)
        except Exception as err:
            raise error.DomeNotFound(err)

    def __del__(self):
        try:
            if self.ser:
                self.ser.disconnect()
        except NameError:
            pass

    @property
    def is_connected(self):
        """True if connected to the hardware or driver."""
        if self.ser:
            return self.ser.is_connected
        return False

    def connect(self):
        """ Connects to the device via the serial port (`self._port`)

        Returns:
            bool:   Returns True if connected, False otherwise.
        """
        if not self.ser:
            self.logger.error('No SerialData instance')
        elif not self.is_connected:
            self.logger.debug('Connecting to dome')
            try:
                self.ser.connect()
                self.logger.info('Dome connected: {}'.format(self.is_connected))
            except OSError as err:
                self.logger.error("OS error: {0}".format(err))
            except error.BadSerialConnection as err:
                self.logger.warning('Could not create serial connection to dome.')
                self.logger.warning('NO DOME CONTROL AVAILABLE\n{}'.format(err))
        else:
            self.logger.debug('Already connected to dome')

        return self.is_connected

    def disconnect(self):
        self.logger.debug("Closing serial port for dome")
        self._is_connected = self.ser.disconnect()

    def verify_connected(self):
        """Throw an exception if not connected."""
        if not self.is_connected:
            raise error.BadSerialConnection(
                msg='Not connected to dome at port {}'.format(self._port))
