import queue as queue_module
import threading


def _dummy_save_func(name, data):
    pass


class SensorRecorder(threading.Thread):
    """Monitors a queue for readings from sensors, records in the store.

    This is a Thread sub-class so that it can run as a deamon.
    """

    def __init__(self,
                 save_func,
                 send_func,
                 legacy_collections=False,
                 max_queue_size=100,
                 **kwargs):
        """
        Args:
            save_func:
                Function to save a reading to a data store.
                Takes two parameters, name and reading.
            send_func:
                Function to send the reading to the messaging system.
                Takes two parameters, name and reading.
            legacy_collections:
                If true, save/send the 'environment' collection.
            max_queue_size:
                Number of readings to allow to accumulate in the queue.
            **kwargs: Any other parameters to threading.Thread.
        """
        kwargs.setdefault('name', 'SensorRecorder')
        kwargs.setdefault('daemon', True)
        assert 'target' not in kwargs
        kwargs['target'] = None
        super().__init__(**kwargs)

        # These are all private and should only be accessed by the public methods.
        self._save_func = save_func or _dummy_save_func
        self._send_func = send_func or _dummy_save_func
        self._legacy_collections = legacy_collections
        self._stop = threading.Event()
        self._latest_all_sensors = {}
        self._readings_queue = queue_module.Queue(maxsize=max_queue_size)

    def stop(self):
        """Tells the thread to stop running.

        Call this before calling Thread.join().
        """
        self._stop.set()
        pass

    def queue(self):
        """Returns the queue to which a sensor should write its readings."""
        return self._readings_queue

    def run(self):
        """Method called by Thread when this is running in its own thread.

        Do not call this directly.
        """
        self._logger.info('SensorRecorder thread {!r} (id {}) starting',
                          threading.current_thread().name, threading.get_ident())
        while not self._stop.is_set():
            reading = self._readings_queue.get(block=True, timeout=2.0)
            if not reading:
                continue
            self._handle_reading(reading)
        self._logger.info('SensorRecorder thread {!r} (id {}) stopping',
                          threading.current_thread().name, threading.get_ident())

    def _handle_reading(self, reading):
        """Store a sensor reading in the database and send a message."""
        name = reading['name']
        self._save_func(name, reading)
        self._send_func(name, reading)

        # Legacy support, where we store all the sensors in an 'environment' collection.
        if self._legacy_collections:
            self._latest_all_sensors[name] = reading
            self._save_func('environment', self._latest_all_sensors)
            self._send_func('environment', self._latest_all_sensors)
