import os
import time
import multiprocessing

from panoptes.utils.logger import get_root_logger
from panoptes.utils.config import load_config
from panoptes.utils.database import PanMongo


class PanProcess(object):
    """ Creates a simple way to launch a separate process """

    def __init__(self, name='PanProcess', **kwargs):
        super().__init__()
        self.name = name

        self.db = None
        self.process = None

        self._loop_delay = kwargs.get('loop_delay', 60)

        self.config = kwargs.get('config', load_config())
        self.logger = kwargs.get('logger', get_root_logger())

        assert self.config is not None, self.logger.warning("Config not set for process")
        assert self.logger is not None, self.logger.warning("Logger not set for process")

        # Setup the actual process
        self.process = multiprocessing.Process(target=self._loop_capture)
        self.process.daemon = True
        self.process.name = 'PanProcess_{}'.format(self.name).replace(' ', '_')

        self._in_loop = False
        self._is_capturing = False

    def start_capturing(self):
        """ Starts the capturing loop for the process

        This calls the `start` method on the actual subprocess. User code will
        typically call this method.
        """

        self.is_capturing = True
        self.logger.info("Staring capture loop for process {}".format(self.process.pid))
        try:
            self.process.start()
        except AssertionError as err:
            self.logger.warning("Can't start process {}: {}".format(self.name, err))

    def stop_capturing(self):
        """ Stops the capturing loop for the process

        This calls the `stop` method on the actual subprocess. User code will
        typically call this method.
        """
        self.logger.info("Stopping capture loop for {}".format(self.process.pid))
        self.is_capturing = False
        while self._in_loop:
            print("\tWaiting for loop to finish")
            time.sleep(int(self._loop_delay / 2))
        else:
            print("Terminating process {} {}".format(self.name, self.process.pid))
            self.process.terminate()
            self.process.join()

    @property
    def process_exists(self):
        """ Checks OS for running process ID (PID) and returns boolean """
        return os.path.exists('/proc/{}'.format(self.process.pid))

    @property
    def is_capturing(self):
        """ Whether or not the loop has started capturing """
        return self._is_capturing

    @is_capturing.setter
    def is_capturing(self, value):
        self._is_capturing = value

    def step(self):
        """ Called once per loop. This is the main method for a subclass to override """
        raise NotImplementedError("Must implement `step` method")

    def _loop_capture(self):
        """ Calls commands to be performed each time through the loop """
        while self.is_capturing:
            self._in_loop = True
            self.step()
            time.sleep(self._loop_delay)
        else:
            self._in_loop = False
            self.logger.info("Stopping loop for {}".format(self.name))
