"""Bisque dome controller using TheSkyX scripting interface.

Provides a Dome implementation that communicates with TheSkyX over TCP using
script templates to perform operations such as connect, open/close slit, park,
unpark, and query status/position.
"""

import os
import time
from string import Template

from panoptes.utils import error
from panoptes.utils.serializers import from_json

from panoptes.pocs import dome
from panoptes.pocs.utils import theskyx


class Dome(dome.AbstractDome):
    """Dome controller backed by TheSkyX.

    Uses TheSkyX's TCP scripting interface with small JavaScript templates to
    perform actions and read status.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the Bisque/TheSkyX dome controller.

        Args:
            *args: Forwarded to AbstractDome.
            **kwargs: May include 'template_dir' to override the scripts directory.
        """
        super().__init__(*args, **kwargs)
        self.theskyx = theskyx.TheSkyX()

        template_dir = kwargs.get("template_dir", self.get_config("dome.template_dir"))
        if template_dir.startswith("/") is False:
            template_dir = os.path.join(os.environ["POCS"], template_dir)

        assert os.path.exists(template_dir), self.logger.warning(
            "Bisque Mounts required a template directory"
        )

        self.template_dir = template_dir
        self._is_parked = True
        self._is_connected = False

    @property
    def is_connected(self):
        """Whether the TheSkyX dome driver reports connected.

        Returns:
            bool: True if connected to TheSkyX.
        """
        return self._is_connected

    @property
    def is_open(self):
        """Whether the dome slit is open.

        Returns:
            bool: True if slit state reads as 'Open'.
        """
        return self.read_slit_state() == "Open"

    @property
    def is_closed(self):
        """Whether the dome slit is closed.

        Returns:
            bool: True if slit state reads as 'Closed'.
        """
        return self.read_slit_state() == "Closed"

    def read_slit_state(self):
        """Query TheSkyX for the current slit state and return a label.

        Returns:
            str: One of 'Open', 'Closed', 'Unknown', or 'Disconnected'.
        """
        if self.is_connected:
            self.write(self._get_command("dome/slit_state.js"))
            response = self.read()

            slit_lookup = {
                0: "Unknown",
                1: "Open",
                2: "Closed",
                3: "Open",
                4: "Closed",
            }

            return slit_lookup.get(response["msg"], "Unknown")
        else:
            return "Disconnected"

    @property
    def status(self):
        """Return a status mapping from TheSkyX.

        Returns:
            dict: Parsed response from the 'dome/status.js' template.
        """
        self.write(self._get_command("dome/status.js"))
        return self.read()

    @property
    def position(self):
        """Return current dome position as reported by TheSkyX.

        Returns:
            dict: Parsed response from the 'dome/position.js' template.
        """
        self.write(self._get_command("dome/position.js"))
        return self.read()

    @property
    def is_parked(self):
        """Whether the dome is parked (per TheSkyX responses)."""
        return self._is_parked

    def connect(self):
        """Connect to the dome controller via TheSkyX.

        Returns:
            bool: True if the connection succeeds.
        """
        if not self.is_connected:
            self.write(self._get_command("dome/connect.js"))
            response = self.read()

            self._is_connected = response["success"]

        return self.is_connected

    def disconnect(self):
        """Disconnect from TheSkyX, closing the slit first if necessary.

        Returns:
            bool: True if now disconnected.
        """
        if self.is_connected:
            if self.is_open:
                self.close()

            self.write(self._get_command("dome/disconnect.js"))
            response = self.read()

            if response["success"]:
                self._is_connected = False

        return not self.is_connected

    def open(self):
        """Command the dome to open the slit and wait until it reports open.

        Returns:
            bool: True if the slit ends up open.
        """
        if self.is_closed:
            self.logger.debug("Opening slit on dome")

            self.write(self._get_command("dome/open_slit.js"))

            while not self.is_open:
                self.logger.debug("Waiting for slit to open")
                time.sleep(1)

        return self.is_open

    def close(self):
        """Command the dome to close the slit and wait until it reports closed.

        Returns:
            bool: True if the slit ends up closed.
        """
        if self.is_open:
            self.logger.debug("Closing slit on dome")

            self.write(self._get_command("dome/close_slit.js"))

            while self.is_open:
                self.logger.debug("Waiting for slit to close")
                time.sleep(1)

        return self.is_closed

    def park(self):
        """Park the dome via TheSkyX and update internal state.

        Returns:
            bool: True if park succeeded.
        """
        if self.is_connected:
            self.write(self._get_command("dome/park.js"))
            response = self.read()

            self._is_parked = response["success"]

        return self.is_parked

    def unpark(self):
        """Unpark the dome via TheSkyX and update internal state.

        Returns:
            bool: True if the dome reports unparked.
        """
        if self.is_connected:
            self.write(self._get_command("dome/unpark.js"))
            response = self.read()

            self._is_parked = not response["success"]

        return not self.is_parked

    def find_home(self):
        """Command TheSkyX to find the dome's home position.

        Returns:
            bool: True if TheSkyX reports success and the dome is now parked at
            home; otherwise returns the last known parked state.
        """
        if self.is_connected:
            self.write(self._get_command("dome/home.js"))
            response = self.read()

            self._is_parked = response["success"]

        return self.is_parked

    ##################################################################################################
    # Communication Methods
    ##################################################################################################

    def write(self, value):
        """Send a script to TheSkyX.

        Args:
            value (str): JavaScript command to execute.

        Returns:
            None
        """
        return self.theskyx.write(value)

    def read(self, timeout=5):
        """Read and parse a response from TheSkyX with a simple timeout loop.

        Args:
            timeout (int): Seconds to wait before giving up.

        Returns:
            dict: Parsed JSON-like object with 'response' and 'success' keys when possible.
        """
        while True:
            response = self.theskyx.read()
            if response is not None or timeout == 0:
                break
            else:
                time.sleep(1)
                timeout -= 1

        # Default object.
        response_obj = {
            "response": response,
            "success": False,
        }
        try:
            response_obj = from_json(response)
        except (TypeError, error.InvalidDeserialization) as e:
            self.logger.warning(f"Error: {e!r}: {response}")

        return response_obj

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def _get_command(self, filename, params=None):
        """Looks up appropriate command for telescope"""

        if filename.startswith("/") is False:
            filename = os.path.join(self.template_dir, filename)

        template = ""
        try:
            with open(filename) as f:
                template = Template(f.read())
        except Exception as e:
            self.logger.warning(f"Problem reading TheSkyX template {filename}: {e}")

        if params is None:
            params = {}

        params.setdefault("async", "true")

        return template.safe_substitute(params)
