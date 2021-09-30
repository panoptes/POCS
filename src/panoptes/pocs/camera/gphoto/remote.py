from typing import List, Union
from threading import Thread

import requests
from collections import deque

from panoptes.pocs.camera.gphoto.canon import Camera as CanonCamera
from pydantic import AnyHttpUrl


class Camera(CanonCamera):
    """A remote gphoto2 camera class."""

    def __init__(self, endpoint: AnyHttpUrl = 'http://localhost:6565', *args, **kwargs):
        """Control a remote gphoto2 camera via the pocs service.

        Interact with a camera via `panoptes.pocs.utils.service.camera`.
        """
        self.endpoint = endpoint
        self.response_queue: deque = deque(maxlen=1)

        super().__init__(*args, **kwargs)

    def command(self, cmd, endpoint: AnyHttpUrl = None):
        """Run the gphoto2 command remotely.

        This assumes the remote camera service is running at the endpoint specified
        on the camera object or passed to the method.
        """
        endpoint = endpoint or self.endpoint

        arguments = ' '.join(cmd)
        # Add the port
        if '--port' not in arguments:
            arguments = f'--port {self.port} {arguments}'
        self.logger.debug(f'Running remote gphoto2 on {endpoint=} with {arguments=}')

        def do_command():
            response = requests.post(endpoint, json=dict(arguments=arguments))
            self.logger.debug(f'Remote gphoto2 {response=!r}')
            if response.ok:
                output = response.json()
                self.logger.debug(f'Response {output=!r}')
                self.response_queue.append(output)
            else:
                self.logger.error(f'Error in remote camera service: {response.content}')

        self._command_proc = Thread(target=do_command, name='RemoteGphoto2Command')
        self._command_proc.start()

    def get_command_result(self, timeout: float = 10) -> Union[List[str], None]:
        """Get the output from the remote camera service."""
        output = None
        try:
            self._command_proc.join(timeout=self._timeout)
            if self._command_proc.is_alive():
                raise TimeoutError
        except TimeoutError:
            self.logger.warning(f'Timeout on exposure process for {self.name}')
        else:
            response = self.response_queue.pop()
            if response['output'] > '':
                output = response['output'].split('\n')
                self.logger.debug(f'Remote gphoto2 output: {output!r}')

            if response['error'] > '':
                error = response['error'].split('\n')
                self.logger.debug(f'Remote gphoto2 error: {error!r}')

        return output

    def _poll_exposure(self, readout_args, *args, **kwargs):
        """Check if remote command has completed."""
        # Camera type specific readout function

        try:
            self._command_proc.join(timeout=self._timeout)
            # Thread should not be alive after join unless we timed out.
            if self._command_proc.is_alive():
                raise TimeoutError
        except TimeoutError:
            self.logger.warning(f'Timeout on exposure process for {self.name}')
        else:
            # Camera type specific readout function
            self._readout(*readout_args)
        finally:
            self.logger.debug(f'Setting exposure event for {self.name}')
            self._is_exposing_event.clear()  # Make sure this gets set regardless of readout errors
