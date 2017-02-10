import socket

from pocs import PanBase


class TheSkyX(PanBase):

    """ A socket connection for communicating with TheSkyX


    """

    def __init__(self, host='localhost', port=3040, connect=True, *args, **kwargs):
        super(TheSkyX, self).__init__()

        self._host = host
        self._port = port

        self._socket = None

        self._is_connected = False
        if connect:
            self.connect()

    @property
    def is_connected(self):
        return self._is_connected

    @property
    def template_dir(self):
        if self._template_dir is None:
            self._template_dir = '{}/bisque_software'.format(self.config['directories']['resources'])

        return self._template_dir

    def connect(self):
        """ Sets up serial connection """
        self.logger.debug('Making TheSkyX connection for mount at {}:{}'.format(self._host, self._port))

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self._host, self._port))
        except ConnectionRefusedError:
            self.logger.warning('Cannot create connection to TheSkyX')
        else:
            self._is_connected = True
            self.logger.debug('Mount connected via TheSkyX')

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
