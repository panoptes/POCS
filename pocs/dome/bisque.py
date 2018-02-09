import json
import os
import time

from string import Template

import pocs.dome
import pocs.utils.theskyx


class Dome(pocs.dome.AbstractDome):
    """docstring for Dome"""

    def __init__(self, *args, **kwargs):
        """"""
        super().__init__(*args, **kwargs)
        self.theskyx = pocs.utils.theskyx.TheSkyX()

        template_dir = kwargs.get('template_dir',
                                  self.config['dome']['template_dir'])
        if template_dir.startswith('/') is False:
            template_dir = os.path.join(os.environ['POCS'], template_dir)

        assert os.path.exists(template_dir), self.logger.warning(
            "Bisque Mounts required a template directory")

        self.template_dir = template_dir

    @property
    def is_connected(self):
        return self._is_connected

    @property
    def is_open(self):
        return self.read_slit_state() == 'Open'

    @property
    def is_closed(self):
        return self.read_slit_state() == 'Closed'

    def read_slit_state(self):
        if self.is_connected:
            self.write(self._get_command('dome/slit_state.js'))
            response = self.read()

            slit_lookup = {
                0: 'Unknown',
                1: 'Open',
                2: 'Closed',
                3: 'Open',
                4: 'Closed',
            }

            return slit_lookup.get(response['msg'], 'Unknown')
        else:
            return 'Disconnected'

    @property
    def status(self):
        return self.read_slit_state()

    def connect(self):
        if not self.is_connected:
            self.write(self._get_command('dome/connect.js'))
            response = self.read()

            self._is_connected = response['success']

        return self.is_connected

    def disconnect(self):
        if self.is_connected:
            if self.is_open:
                self.close_slit()

            self.write(self._get_command('dome/disconnect.js'))
            response = self.read()

            if response["success"]:
                self._is_connected = False

        return not self.is_connected

    def open(self):
        if self.is_closed:
            self.logger.debug("Opening slit on dome")

            self.write(self._get_command('dome/open_slit.js'))

            while not self.is_open:
                self.logger.debug("Waiting for slit to open")
                time.sleep(1)

        return self.is_open

    def close(self):
        if self.is_open:
            self.logger.debug("Closing slit on dome")

            self.write(self._get_command('dome/close_slit.js'))

            while self.is_open:
                self.logger.debug("Waiting for slit to close")
                time.sleep(1)

        return self.is_closed


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
            self.logger.warning(
                "Problem reading TheSkyX template {}: {}".format(filename, e))

        if params is None:
            params = {}

        params.setdefault('async', 'true')

        return template.safe_substitute(params)
