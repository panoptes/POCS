import shutil
import subprocess

import typer
from panoptes.utils.config.client import get_config

from panoptes.pocs.utils.tasks import TaskManager

app = typer.Typer()


@app.command()
def start_backends(
        config_key: str = typer.Option('celery',
                                       help='The key to use to look up the celery config.')
):
    """Start the celery backends specified by the config."""
    celery_config = get_config(config_key)
    typer.echo('Starting celery backends.')
    TaskManager.start_celery_backends(celery_config)


@app.command()
def stop_backends(
        remove: bool = typer.Option(False,
                                    help='If running containers should be removed or just stopped.'),
        config_key: str = typer.Option('celery',
                                       help='The key to use to look up the celery config.')

):
    """Stop the running celery backends specified by the config."""
    celery_config = get_config(config_key)
    typer.echo('Stopping celery backends.')
    TaskManager.stop_celery_backends(celery_config, remove=remove)


@app.command()
def start_worker(
        worker: str = typer.Option(..., help='The name of the worker to start.'
                                             'Can be an absolute namespace or the name of a module'
                                             'in `panoptes.pocs.utils.service`.'),
        queue: str = typer.Option(None,
                                  help='The name of the queue to use for the worker,'
                                       'defaults to class name'),
        loglevel: str = typer.Option('INFO', help='The name of a valid log level.'),
):
    """Starts a worker thread for the given piece of hardware."""
    queue = queue or str(worker)

    # TODO this could be a better check for module name, perhaps with load_module.
    if '.' not in worker:
        worker = f'panoptes.pocs.utils.service.{worker}'

    typer.echo(f'Starting celery {worker=} with {queue=}')

    subprocess.run([
        shutil.which('celery'),
        '-A', worker, 'worker',
        '-Q', queue,
        '--loglevel', loglevel
    ])


if __name__ == '__main__':
    app()
