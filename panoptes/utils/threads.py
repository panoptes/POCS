import threading

from ..utils.logger import has_logger


@has_logger
class PanThread(threading.Thread):

    """Creates threads with common interface for project. Supports
    the stop() method.

    """

    def __init__(self, target, args=list()):
        super().__init__(target=target, args=args)
        self._stop = threading.Event()

    def stop(self):
        """Stops the thread by calling the threading.Event
        set() method. Thread is then responsible for checking
        """
        self._stop.set()

    def is_stopped(self):
        """Reports if thread is stopped"""
        return self._stop.is_set()

    def wait(self, wait_time=1):
        """Wrapper around the threading.Event wait() method"""
        self._stop.wait(wait_time)
