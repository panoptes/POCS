from typing import List, Union

from panoptes.pocs.camera.gphoto.remote import Camera as RemoteCamera
from panoptes.pocs.utils import error
from panoptes.pocs.utils.tasks import TaskManager, RunTaskMixin
from panoptes.utils.utils import get_quantity_value


class Camera(RemoteCamera, RunTaskMixin):
    """A remote gphoto2 camera class that can call local or remote celery tasks."""

    def __init__(self, *args, **kwargs):
        """Control a remote gphoto2 camera via a celery task.

        Interact with a camera via `panoptes.pocs.utils.service.camera`.
        """
        super().__init__(*args, **kwargs)

        self.celery_app = TaskManager.create_celery_app_from_config()

        self.task = None
        self.logger.debug("Creating Canon DSLR GPhoto2 camera celery task manager")

    @property
    def is_exposing(self):
        # Check if the last task was successful.
        if self.task is not None and self.task.state == 'SUCCESS':
            self.task = None

        return self.task is not None

    def command(self, cmd, queue=None, **kwargs):
        """Run a remote celery task attached to a camera. """

        if self.is_exposing:
            raise error.CameraBusy()

        queue = queue or self.name

        arguments = ' '.join(cmd)

        self.logger.debug(f'Running remote gphoto2 task with {arguments=} to {queue=}')
        self.task = self.call_task('camera.command', args=[arguments], queue=queue)

    def get_command_result(self, timeout: float = 10) -> Union[List[str], None]:
        """Get the output from the remote camera task, blocking up to timeout."""
        cmd_result = self.task.get(timeout=timeout)

        self.logger.debug(f'Full results from command {cmd_result!r}')

        # Clear task.
        self.task = None

        # Return just the actual output. TODO error checking?
        return cmd_result['output']

    def _start_exposure(self,
                        seconds=None,
                        filename=None,
                        dark=False,
                        header=None,
                        iso=100,
                        *args, **kwargs):
        """Start the exposure using a Celery Task. """
        # Make sure we have just the value, no units
        seconds = get_quantity_value(seconds)

        self.task = self.call_task('camera.release_shutter', args=[seconds])

        return filename, header
