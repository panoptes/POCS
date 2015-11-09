import os
import shutil
import subprocess

from ..logger import has_logger
from .. import error


@has_logger
class PanIndiServer(object):

    """ A module to start an INDI server

    Args:
        drivers(dict):  Dict of valid drivers for indiserver to start, defaults to
            {'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}
        fifo(str):      Path to FIFO file of running indiserver
    """

    def __init__(self, fifo='/tmp/pan_indiFIFO'):
        self._indiserver = shutil.which('indiserver')

        assert self._indiserver is not None, error.PanError("Cannot find indiserver command")

        # Start the server
        self._fifo = fifo

        try:
            self._proc = self.start()
        except Exception as e:
            self.logger.warning("Problem with staring the INDI server: {}".format(e))

        self._connected = False
        self.logger.debug("PanIndiServer created. PID: {}".format(self._proc))


##################################################################################################
# Properties
##################################################################################################

    @property
    def is_connected(self):
        """ INDI Server connection

        Tests whether running PID exists
        """
        try:
            self._connected = os.path.exists('/proc/{}'.format(self._proc.pid))
        except Exception:
            self.logger.warning("Error checking for PID {}".format(self._proc.pid))

        return self._connected

##################################################################################################
# Methods
##################################################################################################

    def start(self, *args, **kwargs):
        """ Start an INDI server.

        Host, port, and drivers must be configured in advance.

        Returns:
            _proc(process):     Returns process from `subprocess.Popen`
        """

        if not os.path.exists(self._fifo):
            try:
                os.mkfifo(self._fifo)
            except Exception as e:
                raise error.InvalidCommand("Can't open fifo at {} \t {}".format(self._fifo, e))

            cmd = [self._indiserver]

            opts = args if args else ['-m', '100', '-f', self._fifo]
            cmd.extend(opts)

            try:
                self.logger.debug("Starting INDI Server: {}".format(cmd))
                self._proc = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                self.logger.debug("INDI server started. PID: {}".format(self._proc.pid))
            except Exception as e:
                self.logger.warning("Cannot start indiserver on {}:{}. {}".format(self.host, self.port, e))

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

        if os.path.exists(self._fifo):
            self.logger.debug("Unlinking FIFO {}".format(self._fifo))
            os.unlink(self._fifo)
