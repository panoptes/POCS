import time
from pprint import pprint

import typer

from panoptes.pocs.sensor.remote import RemoteMonitor
from panoptes.pocs.utils.logger import get_logger

app = typer.Typer()
logger = get_logger(stderr_log_level='ERROR')


@app.callback()
def main(context: typer.Context):
    context.params.update(context.parent.params)
    verbose = context.params['verbose']
    if verbose:
        typer.echo(f'Command options from power: {context.params!r}')


@app.command()
def monitor(
        name: str,
        endpoint: str = 'http://127.0.0.1:6564',
        store_result: bool = True,
        read_frequency: int = 60,
        verbose: bool = False,
):
    """Continuously read remote sensor, optionally storing results."""
    remote_monitor = RemoteMonitor(endpoint_url=endpoint, sensor_name=name)
    try:
        while True:
            result = remote_monitor.capture(store_result=store_result)
            if verbose:
                pprint(result)
            time.sleep(read_frequency)
    except KeyboardInterrupt:
        typer.echo(f'Shutting down monitor script for {name}')


if __name__ == "__main__":
    app()
