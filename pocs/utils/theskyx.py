import socket

from pocs import PanBase


class TheSkyX(PanBase):

    """ A socket connection for communicating with TheSkyX


    """

    def __init__(self, host='localhost', port=3040, connect=True, *args, **kwargs):
        super(TheSkyX, self).__init__(*args, **kwargs)

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

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self._host, self._port))
        except ConnectionRefusedError:
            self.logger.warning('Cannot create connection to TheSkyX')
        else:
            self._is_connected = True
            self.logger.info('Connected to TheSkyX via {}:{}'.format(self._host, self._port))

    def write(self, value):
        assert type(value) is str
        self.socket.sendall(value.encode())

    def read(self, timeout=5):
        self.socket.settimeout(timeout)
        response = None

        try:
            response = self.socket.recv(4096).decode()
            if '|' in response:
                response, err = response.split('|')
            if 'No error' not in err:
                self.logger.warning("Mount error: {}".format(err))
        except socket.timeout:
            pass

        return response
