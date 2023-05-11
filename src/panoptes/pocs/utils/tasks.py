import docker
import docker.errors
import celery
from loguru import logger
from panoptes.utils.config.client import get_config


class TaskManager:
    """Simple celery task manager."""

    @classmethod
    def create_celery_app_from_config(cls, config=None, config_key='celery'):
        """Create an instance of the class from the config.

        If `config` is `None` (the default) then attempt a lookup in the config
        server using the `config_key`.
        """
        config = config or get_config(config_key)
        if config:
            logger.info(f'Creating Celery app with {config=!r}')
            celery_app = celery.Celery()
            celery_app.config_from_object(config)
            print(f'Created {celery_app}')

            return celery_app

    @classmethod
    def start_celery_backends(cls, celery_config: dict):
        """Use the python docker binders to control required celery backends."""
        docker_client = docker.from_env()

        # Start the messaging and result backend services.
        for service_config in celery_config['service']:
            service_name = service_config['name']
            service_image = service_config['image']

            print(f'Starting {service_name} container using {service_image=}')
            try:
                # Try to start existing container first.
                container = docker_client.containers.get(service_name)
                container.start()
            except docker.errors.NotFound:
                print(f'Creating new container for {service_name}')
                # Or create a new one.
                docker_client.containers.run(
                    service_image,
                    ports=service_config.get('ports'),
                    name=service_name,
                    detach=True,
                )
                print(f'{service_name} started')
            except docker.errors.APIError as e:
                print(f'{service_name} already running: {e!r}')

    @classmethod
    def stop_celery_backends(cls, celery_config: dict, remove: bool = False):
        """Stop the docker containers running the celery backends."""
        docker_client = docker.from_env()

        # Stop the messaging and result backends.
        # Start the messaging and result backend services.
        for service_config in celery_config['service']:
            service_name = service_config['name']
            logger.info(f'Stopping {service_name} container')

            try:
                container = docker_client.containers.get(service_name)
                container.stop()

                if remove:
                    logger.info(f'Removing {service_name} container')
                    container.remove()
            except docker.errors.APIError:
                logger.info(f'{service_name} not running')


class RunTaskMixin:
    """A mixin class for running celery tasks and getting results."""
    celery_app: celery.Celery

    def call_task(self, name: str = '', **kwargs) -> celery.Task:
        """Call a celery task.

        Thin-wrapper around `self.celery.send_task` and all `kwargs` are passed
        along as-is.

        If `queue` is not given in `kwargs` the value will be set to the name
        of the class (i.e. `queue = self.__class__`).

        Checks for valid `self.celery` object and logs a warning if
        unavailable.
        """
        queue = kwargs.setdefault('queue', self.__class__)
        logger.debug(f'Calling task {name} with {kwargs=!r} on {queue=}')
        task = self.celery_app.send_task(name, **kwargs)
        logger.debug(f'{name} task started with {task.id=}')

        return task

    def get_task(self, task_id: str) -> celery.Task:
        """Get the task via its ID number."""
        return self.celery_app.AsyncResult(task_id)
