import multiprocessing

from panoptes.utils.logger import get_root_logger


class PanProcess(object):
    """ Creates a simple way to launch a separate process """

    def __init__(self, name='PanProcess', target_method=None, **kwargs):
        assert target_method is not None

        self.name = name

        self.db = None
        self.process = None

        self._loop_delay = kwargs.get('loop_delay', 60)

        self.logger = kwargs.get('logger', get_root_logger())

        assert self.logger is not None, self.logger.warning("Logger not set for process")

        self.logger.info("Creating separate process")
        # Setup the actual process
        self.process = multiprocessing.Process(target=target_method)
        self.process.daemon = True
        self.process.name = 'PanProcess_{}'.format(self.name).replace(' ', '_')
        self.logger.info("Separate process created")

    def start(self):
        """ Starts the capturing loop for the process

        This calls the `start` method on the actual subprocess. User code will
        typically call this method.
        """

        self.logger.info("Starting capture loop for process {}".format(self.process.pid))
        try:
            self.process.start()
        except AssertionError as err:
            self.logger.warning("Can't start process {}: {}".format(self.name, err))

    def stop(self):
        """ Stops the capturing loop for the process

        This calls the `stop` method on the actual subprocess. User code will
        typically call this method.
        """
        self.logger.info("Stopping capture loop for {}".format(self.process.pid))
        self.process.terminate()
        self.process.join()
