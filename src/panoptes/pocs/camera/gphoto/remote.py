from collections import deque
from threading import Thread
from typing import List, Union

import requests
from pydantic import AnyHttpUrl

from panoptes.pocs.camera.gphoto.canon import Camera as CanonCamera


class Camera(CanonCamera):
    """A remote gphoto2 camera class."""

    def __init__(self, endpoint: AnyHttpUrl = "http://localhost:6565", *args, **kwargs):
        """Control a remote gphoto2 camera via the pocs service.

        Interact with a camera via `panoptes.pocs.utils.service.camera`.
        """
        self.endpoint = endpoint
        self.response_queue: deque = deque(maxlen=1)

        super().__init__(*args, **kwargs)

    @property
    def is_exposing(self):
        if self._command_proc is not None and self._command_proc.is_alive() is False:
            self._is_exposing_event.clear()

        return self._is_exposing_event.is_set()

    def command(self, cmd, endpoint: AnyHttpUrl = None):
        """Run the gphoto2 command remotely.

        This assumes the remote camera service is running at the endpoint specified
        on the camera object or passed to the method.
        """
        endpoint = endpoint or self.endpoint

        arguments = " ".join(cmd)
        # Add the port
        if "--port" not in arguments:
            arguments = f"--port {self.port} {arguments}"
        self.logger.debug(f"Running remote gphoto2 on {endpoint=} with {arguments=}")

        def do_command():
            response = requests.post(endpoint, json=dict(arguments=arguments))
            self.logger.debug(f"Remote gphoto2 {response=!r}")
            if response.ok:
                output = response.json()
                self.logger.debug(f"Response {output=!r}")
                self.response_queue.append(output)
                self._is_exposing_event.clear()
            else:
                self.logger.error(f"Error in remote camera service: {response.content}")

        self._command_proc = Thread(target=do_command, name="RemoteGphoto2Command")
        self._command_proc.start()

    def get_command_result(self, timeout: float = 10) -> Union[List[str], None]:
        """Get the output from the remote camera service."""
        output = None
        try:
            self._command_proc.join(timeout=self.timeout)
            if self._command_proc.is_alive():
                raise TimeoutError
        except TimeoutError:
            self.logger.warning(f"Timeout on exposure process for {self.name}")
        else:
            response = self.response_queue.pop()
            if response["output"] > "":
                output = response["output"].split("\n")
                self.logger.debug(f"Remote gphoto2 output: {output!r}")

            if response["error"] > "":
                error = response["error"].split("\n")
                self.logger.debug(f"Remote gphoto2 error: {error!r}")

        return output

    def _create_fits_header(self, seconds, dark=None, metadata=None) -> dict:
        fits_header = super(Camera, self)._create_fits_header(seconds, dark=dark, metadata=metadata)
        return {k.lower(): v for k, v in dict(fits_header).items()}
