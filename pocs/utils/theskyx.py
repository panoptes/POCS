import os
import time
import json
from socket import socket, AF_INET, SOCK_STREAM, SHUT_RDWR
from string import Template

from pocs.base import PanBase
from pocs.utils import error


class TheSkyX(PanBase):

    """ A socket connection for communicating with TheSkyX


    """

    def __init__(self, host='localhost', port=3040, template_dir=None, *args, **kwargs):
        super(TheSkyX, self).__init__(*args, **kwargs)

        assert template_dir is not None and os.path.exists(template_dir)

        self._host = host
        self._port = port
        self.template_dir = template_dir

    def query(self, cmd_file, params=None, retries=0):
        """Query TheSkyX and parse response.

        This will attempt to parse the response as JSON and if fails will
        put the response in another object along with success key.

        Note: The underlying theskyx.query will add the necessary negotiation
        key.

        Args:
            cmd_file (str): Relative path to javascript file containing command.
                This should be a relative path and not include the extension. See
                appropriate yaml file lookup.
            params (dict, optional): Optional parameters to substitute into the template.
            retries (int, optional): Retry reading number of times, defaults

        Returns:
            dict: Parse response. Always includes a `success` key.
        """
        response_obj = {'success': False}
        command = self._get_command(cmd_file, params=params)
        while True:
            response = self.theskyx._query(command)
            if response is not None or retries == 0:
                break
            else:
                time.sleep(1)
                retries -= 1

        if response is None:
            return response_obj

        try:
            response_obj = json.loads(response)
            # If we parse as json and doesn't include a success flag, assume not ok.
            if 'success' not in response_obj:
                response_obj['success'] = False
        except TypeError as e:
            self.logger.warning("Error: {}".format(e, response))
        except json.JSONDecodeError as e:
            self.logger.warning("Can't decode JSON response from TheSkyX")
            self.logger.warning(e)
            self.logger.warning(response)
            response_obj = {
                "response": response,
                "msg": response,  # Some things expect this key
                "success": False,
            }

        return response_obj

    def _query(self, command):
        """Query TheSkyX and get response.

        Note: This will create and destroy a socket for each communication
        attempt. Reads a set 2048 bytes from socket.

        Args:
            command (str): A valid js command to send to TheSkyX. Command

        Returns:
            str: Raw decoded response from TheSkyX.

        Raises:
            TheSkyXError: Exception raised if anything goes wrong.
        """
        try:
            self.logger.debug('Making TheSkyX connection at {}:{}'.format(self._host, self._port))
            self.logger.debug("Command: {!r}", command)
            socket_obj = socket(AF_INET, SOCK_STREAM)
            socket_obj.connect((self.host, self.port))
            socket_obj.send(('/* Java Script */\n' +
                             '/* Socket Start Packet */\n' +
                             command +
                             '\n/* Socket End Packet */\n'))
            response = socket_obj.recv(2048).decode()
            self.logger.debug("Response: {!r}", response)
            socket_obj.shutdown(SHUT_RDWR)
            socket_obj.close()
            return response.split("|")[0]
        except Exception as e:
            raise error.TheSkyXError(
                "Connection to {}:{} failed. :{}".format(self._host, self._port, e))

    def _get_command(self, cmd, params=None):
        """ Looks up appropriate command template """

        cmd_info = self.commands.get(cmd)

        try:
            filename = cmd_info['file']
        except KeyError:
            raise error.InvalidCommand("TheSkyX command file not found: {}".format(cmd_info))

        if filename.startswith('/') is False:
            filename = os.path.join(self.template_dir, filename)

        template = ''
        try:
            with open(filename, 'r') as f:
                template = Template(f.read())
        except Exception as e:
            self.logger.warning("Problem reading TheSkyX template {}: {}".format(filename, e))

        if params is None:
            params = {}

        params.setdefault('async', 'true')

        return template.safe_substitute(params)
