import os
import time

import pocs.dome
from pocs.utils import theskyx


class Dome(pocs.dome.AbstractDome):
    """docstring for Dome"""

    def __init__(self, *args, **kwargs):
        """"""
        super().__init__(*args, **kwargs)

        template_dir = kwargs.get('template_dir',
                                  self.config['dome']['template_dir'])
        if template_dir.startswith('/') is False:
            template_dir = os.path.join(os.environ['POCS'], template_dir)

        assert os.path.exists(template_dir), self.logger.warning(
            "Bisque domes require a template directory")

        self.theskyx = theskyx.TheSkyX(template_dir=template_dir)

    @property
    def is_open(self):
        return self.read_slit_state() == 'Open'

    @property
    def is_closed(self):
        return self.read_slit_state() == 'Closed'

    def read_slit_state(self):
        if self.is_connected:
            response = self.query('slit_state')

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
            response = self.query('connect')

            self._is_connected = response['success']

        return self.is_connected

    def disconnect(self):
        if self.is_connected:
            if self.is_open:
                self.close_slit()

            response = self.query('disconnect')

            if response["success"]:
                self._is_connected = False

        return not self.is_connected

    def open(self):
        if self.is_closed:
            self.logger.debug("Opening slit on dome")

            self.query('open_slit')

            while not self.is_open:
                self.logger.debug("Waiting for slit to open")
                time.sleep(1)

        return self.is_open

    def close(self):
        if self.is_open:
            self.logger.debug("Closing slit on dome")

            self.query('close_slit')

            while self.is_open:
                self.logger.debug("Waiting for slit to close")
                time.sleep(1)

        return self.is_closed
