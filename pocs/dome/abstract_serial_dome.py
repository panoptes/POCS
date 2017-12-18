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
        # TODO(jamessynge): Switch to passing configuration of serial port in as a sub-section
        # of the dome config in the YAML. That way we don't intermingle serial settings and
        # any other settings required.
        cfg = self._dome_config
        self._port = cfg.get('port')
        if not self._port:
            msg = 'No port specified in the config for dome: {}'.format(cfg)
            self.logger.error(msg)
            raise error.DomeNotFound(msg=msg)

        baudrate = int(cfg.get('baudrate', 9600))

        # Setup our serial connection to the given port.
        self.serial = None
        try:
            self.serial = rs232.SerialData(port=self._port, baudrate=baudrate)
        except Exception as err:
            raise error.DomeNotFound(err)

    def __del__(self):
        try:
            if self.serial:
                self.serial.disconnect()
        except AttributeError:
            pass

    @property
    def is_connected(self):
        """True if connected to the hardware or driver."""
        if self.serial:
            return self.serial.is_connected
        return False

    def connect(self):
        """Connects to the device via the serial port, if disconnected.

        Returns:
            bool:   Returns True if connected, False otherwise.
        """
        if not self.is_connected:
            self.logger.debug('Connecting to dome')
            try:
                self.serial.connect()
                self.logger.info('Dome connected: {}'.format(self.is_connected))
            except OSError as err:
                self.logger.error("OS error: {0}".format(err))
            except error.BadSerialConnection as err:
                self.logger.warning(
                    'Could not create serial connection to dome\n{}'.format(err))
        else:
            self.logger.debug('Already connected to dome')

        return self.is_connected

    def disconnect(self):
        self.logger.debug("Closing serial port for dome")
        self.serial.disconnect()

    def verify_connected(self):
        """Throw an exception if not connected."""
        if not self.is_connected:
            raise error.BadSerialConnection(
                msg='Not connected to dome at port {}'.format(self._port))
