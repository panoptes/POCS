import subprocess

from astropy import units as u

from ..utils import error

from .camera import AbstractCamera

from .camera import SBIGDriver


class Camera(AbstractCamera):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.debug("Initializing simulator camera")

        # Simulator
        self._serial_number = '999999'

    def connect(self):
        """ Connect to camera simulator
        The simulator merely markes the `connected` property.
        """
        self._connected = True
        self.logger.debug('Connected')

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """ Take an exposure for given number of seconds """

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        if seconds.value > 5:
            self.logger.debug("Trimming camera simulator exposure to 5 s")
            seconds = 5 * u.second

        self.logger.debug('Taking {} second exposure on {}'.format(seconds, self.name))

        # Simulator just sleeps
        run_cmd = ["sleep", str(seconds.value)]

        # Send command to camera
        try:
            proc = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        except error.InvalidCommand as e:
            self.logger.warning(e)

        return proc
