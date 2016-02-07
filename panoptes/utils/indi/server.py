import os
import shutil
import subprocess

from ..logger import get_logger, get_root_logger
from .. import error


class PanIndiServer(object):

    """ A module to start an INDI server

    Args:
        drivers(dict):  Dict of valid drivers for indiserver to start, defaults to
            {'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}
        fifo(str):      Path to FIFO file of running indiserver
    """

    def __init__(self, drivers=[], **kwargs):

        # self.logger = get_logger(self)
        self.logger = get_root_logger()
        self._indiserver = shutil.which('indiserver')

        assert self._indiserver is not None, error.PanError("Cannot find indiserver command")

        self.drivers = drivers
        self._proc = None

        try:
            # Start the server
            self.start()
        except Exception as e:
            self.logger.warning("Problem with staring the INDI server: {}".format(e))

        self._connected = False
        self.logger.debug("PanIndiServer created. PID: {}".format(self._proc.pid))


##################################################################################################
# Properties
##################################################################################################

    @property
    def is_connected(self):
        """ INDI Server connection

        Tests whether running PID exists
        """
        return os.getpgid(self._proc.pid)

##################################################################################################
# Methods
##################################################################################################

    def start(self, *args, **kwargs):
        """ Start an INDI server.

        Host, port, and drivers must be configured in advance.

        Returns:
            _proc(process):     Returns process from `subprocess.Popen`
        """

        cmd = [self._indiserver]

        opts = args if args else ['-m', '100']
        cmd.extend(opts)
        cmd.extend(self.drivers)

        try:
            self.logger.debug("Starting INDI Server: {}".format(cmd))
            self._proc = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            self.logger.debug("INDI server started. PID: {}".format(self._proc.pid))
        except Exception as e:
            self.logger.warning("Cannot start indiserver: {}".format(e))

    def stop(self):
        """ Stops the INDI server """
        if self._proc:
            if os.getpgid(self._proc.pid):
                self.logger.debug("Shutting down INDI server (PID {})".format(self._proc.pid))

                try:
                    outs, errs = self._proc.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    outs, errs = self._proc.communicate()

            self.logger.debug("Output from INDI server: {}".format(outs))