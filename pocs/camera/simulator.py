import subprocess

from astropy import units as u

from ..utils import error

from .camera import AbstractCamera


class Camera(AbstractCamera):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Initializing simulator camera")

        # Simulator
        self._serial_number = '999999'
        self._file_num = 0

    @property
    def uid(self):
        """ Return a unique id for the camera

        This returns the first six digits of the unique serial number

        Returns:
            int:    Unique hardware id for camera
        """
        return self._serial_number[0:6]

    def connect(self):
        """ Connect to camera simulator

        The simulator merely markes the `connected` property.
        """
        self._connected = True
        self.logger.debug('Connected')

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug('Taking {} second exposure on {}'.format(seconds, self.name))

        # Simulator just sleeps
        run_cmd = ["sleep", str(seconds.value)]

        # Send command to camera
        try:
            proc = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        except error.InvalidCommand as e:
            self.logger.warning(e)

        return proc
