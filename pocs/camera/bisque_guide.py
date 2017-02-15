import json
import os
import time

from string import Template

from .. import PanBase
from ..utils.theskyx import TheSkyX


class Guide(PanBase):

    """docstring for Dome"""

    def __init__(self, *args, **kwargs):
        """"""
        super().__init__(*args, **kwargs)
        self.theskyx = TheSkyX()

        template_dir = kwargs.get('template_dir', self.config['guider']['template_dir'])
        if template_dir.startswith('/') is False:
            template_dir = os.path.join(os.environ['POCS'], template_dir)

        assert os.path.exists(template_dir), self.logger.warning("Bisque guider requires a template directory")

        self.template_dir = template_dir

        self._is_connected = False
        self._is_guiding = False

    @property
    def is_connected(self):
        return self._is_connected

    @property
    def is_open(self):
        return self.slit_state == 'Open'

    @property
    def is_closed(self):
        return self.slit_state == 'Closed'

    @property
    def is_guiding(self):
        return self._is_guiding

    def connect(self):
        if not self.is_connected:
            self.logger.debug("Connecting to guide camera")
            self.write(self._get_command('guider/connect.js'))
            response = self.read()
            self.logger.debug("Guider: {}".format(response))

            self._is_connected = response['success']

        return self.is_connected

    def disconnect(self):
        if self.is_connected:

            self.logger.debug("Disconnecting guide camera")
            self.write(self._get_command('guider/disconnect.js'))
            response = self.read()

            if response["success"]:
                self._is_connected = False

        return not self.is_connected

    def start_guiding(self):
        if self.is_connected:
            if not self.is_guiding:

                self.write(self._get_command('guider/start_guiding.js'))
                response = self.read()

                if response["success"]:
                    self._is_guiding = True

        return not self.is_guiding

    def stop_guiding(self):
        if self.is_connected:
            if self.is_guiding:

                self.write(self._get_command('guider/stop_guiding.js'))
                response = self.read()

                if response["success"]:
                    self._is_guiding = False

        return not self.is_guiding


##################################################################################################
# Communication Methods
##################################################################################################

    def write(self, value):
        return self.theskyx.write(value)

    def read(self, timeout=5):
        while True:
            response = self.theskyx.read()
            if response is not None or timeout == 0:
                break
            else:
                time.sleep(1)
                timeout -= 1

        try:
            response_obj = json.loads(response)
        except TypeError as e:
            self.logger.warning("Error: {}".format(e, response))
        except json.JSONDecodeError as e:
            response_obj = {
                "response": response,
                "success": False,
            }

        return response_obj

##################################################################################################
# Private Methods
##################################################################################################

    def _get_command(self, filename, params=None):
        """ Looks up appropriate command for telescope """

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

        params.setdefault('async', 'false')

        return template.safe_substitute(params)
