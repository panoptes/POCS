import time
from typing import Optional

import typer
from rich import print

from panoptes.pocs.sensor.remote import RemoteMonitor
from panoptes.pocs.utils.logger import get_logger

app = typer.Typer()
logger = get_logger(stderr_log_level="ERROR")


@app.callback()
def main(context: typer.Context):
    context.params.update(context.parent.params)
    verbose = context.params["verbose"]
    if verbose:
        print(f"Command options from power: {context.params!r}")


@app.command()
def monitor(
    sensor_name: str,
    endpoint: Optional[str] = typer.Option(
        None,
        help="The remote endpoint to read. "
        "If not provided, use the config key "
        '"environment.<sensor_name>.url".',
    ),
    store: bool = typer.Option(True, help="If result should be stored in file database."),
    read_frequency: int = typer.Option(60, help="Read frequency in seconds."),
    verbose: bool = False,
):
    """Continuously read remote sensor, optionally storing results."""
    remote_monitor = RemoteMonitor(endpoint_url=endpoint, sensor_name=sensor_name)
    try:
        while True:
            result = remote_monitor.capture(store_result=store)
            if verbose:
                print(result)
            time.sleep(read_frequency)
    except KeyboardInterrupt:
        print(f"[red]Shutting down monitor script for {sensor_name}")


if __name__ == "__main__":
    app()
