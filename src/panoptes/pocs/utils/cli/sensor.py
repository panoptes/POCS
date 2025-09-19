"""Typer CLI for monitoring remote sensors exposed via HTTP endpoints."""
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
    """Common options setup for all sensor CLI commands.

    Args:
        context: Typer context used to access shared options.

    Returns:
        None
    """
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
    """Continuously read a remote sensor, optionally storing results.

    Args:
        sensor_name: Name of the sensor (used for looking up default endpoint in config).
        endpoint: Optional override for the sensor endpoint URL.
        store: If True, persist readings to the local JSON database.
        read_frequency: Polling interval in seconds between readings.
        verbose: If True, echo readings to the console.

    Returns:
        None
    """
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
