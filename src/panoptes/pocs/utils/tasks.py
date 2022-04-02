import docker
import docker.errors
import celery
from loguru import logger
from panoptes.utils.config.client import get_config
from pydantic import BaseModel, BaseSettings, AmqpDsn, RedisDsn


class MessagingConfig(BaseModel):
    container: str = 'rabbitmq'
    broker_url: AmqpDsn = 'amqp://guest:guest@localhost:5672'
    port: int = 5672


class ResultsConfig(BaseModel):
    container: str = 'redis'
    results_backend: RedisDsn = 'redis://localhost:6379'
    port: int = 6379


class CeleryConfig(BaseSettings):
    messaging: MessagingConfig = MessagingConfig()
    results: ResultsConfig = ResultsConfig()


class TaskManager:
    """Simple celery task manager."""

    @classmethod
    def celery_from_config(cls, config=None, config_key='celery'):
        """Create an instance of the class from the config.

        If `config` is `None` (the default) then attempt a lookup in the config
        server using the `config_key`.
        """
        config = config or get_config(config_key)
        if config:
            logger.info(f'Creating Celery app with {config=!r}')
            celery_app = celery.Celery().config_from_object(dict(
                broker_url=config['messaging']['broker_url'],
                result_backend=config['results']['result_backend']
            ))

            return celery_app

    @classmethod
    def start_celery_backends(cls, celery_config: dict):
        """Use the python docker binders to control required celery backends."""
        docker_client = docker.from_env()

        # Start the messaging and result backends.
        for container_type in ['messaging', 'results']:
            container_config = celery_config.get(container_type)
            container_name = f'pocs-{container_type}'

            print(f'Starting {container_name} container')
            try:
                # Try to start existing container first.
                container = docker_client.containers.get(container_name)
                container.start()
            except docker.errors.NotFound:
                print(f'Creating new container for {container_name}')
                # Or create a new one.
                docker_client.containers.run(
                    container_config['service'],
                    ports=container_config['ports'],
                    name=container_name,
                    detach=True,
                )
                print(f'{container_name} started')
            except docker.errors.APIError as e:
                print(f'{container_type} already running: {e!r}')

    @classmethod
    def stop_celery_backends(cls, celery_config: dict, remove: bool = False):
        """Stop the docker containers running the celery backends."""
        docker_client = docker.from_env()

        # Stop the messaging and result backends.
        for container_type in ['messaging', 'results']:
            try:
                container_config = celery_config.get(container_type)
                container_name = f'pocs-{container_type}'
                container = docker_client.containers.get(container_name)

                logger.info(f'Stopping {container_name} container')
                container.stop()

                if remove:
                    logger.info(f'Removing {container_name} container')
                    container.remove()
            except docker.errors.APIError:
                logger.info(f'{container_name} already running')


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
