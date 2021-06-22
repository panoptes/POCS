import socket

from panoptes.utils import error
from panoptes.pocs.utils.logger import get_logger


class TheSkyX(object):
    """ A socket connection for communicating with TheSkyX


    """

    def __init__(self, host='localhost', port=3040, connect=True, *args, **kwargs):
        self.logger = get_logger()

        self._host = host
        self._port = port

        self._socket = None

        self._is_connected = False
        if connect:
            self.connect()

    @property
    def is_connected(self):
        return self._is_connected

    def connect(self):
        """ Sets up serial connection """
        self.logger.debug('Making TheSkyX connection at {}:{}'.format(self._host, self._port))
        if not self.is_connected:

            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((self._host, self._port))
            except ConnectionRefusedError:
                self.logger.warning('Cannot create connection to TheSkyX')
            else:
                self._is_connected = True
                self.logger.info('Connected to TheSkyX via {}:{}'.format(self._host, self._port))

    def write(self, value):
        try:
            assert isinstance(value, str)
            self.socket.sendall(value.encode())
        except AttributeError:
            raise error.BadConnection("Not connected to TheSkyX")

    def read(self, timeout=5):
        try:
            self.socket.settimeout(timeout)
            response = None
            err = None

            try:
                response = self.socket.recv(2048).decode()
                if '|' in response:
                    response, err = response.split('|')

                if 'Error:' in response:
                    response, err = response.split(':')

                if err is not None and 'No error' not in err:
                    if 'Error = 303' in err:
                        raise error.TheSkyXKeyError("Invalid TheSkyX key")

                    raise error.TheSkyXError(err)
            except socket.timeout:  # pragma: no cover
                raise error.TheSkyXTimeout()

            return response
        except AttributeError:
            raise error.BadConnection("Not connected to TheSkyX")
