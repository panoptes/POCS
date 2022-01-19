from contextlib import suppress
from typing import Optional

import typer
import requests

app = typer.Typer()


def server_running(host: str = 'localhost', port: int = 6564):
    """Check if the config server is running"""
    # NOTE: A bug in server_is_running means we cannot specify the port.
    is_running = False
    with suppress(requests.exceptions.ConnectionError):
        is_running = requests.get(f'http://{host}:{port}').ok

    if is_running is None or is_running is False:
        run_status = '[bold red]:x: NOT RUNNING[/bold red]'
    else:
        run_status = '[bold green]:heavy_check_mark: RUNNING[/bold green]'

    print(f'Power Monitor status: {run_status}')

    return is_running


@app.command()
def status(
        host: Optional[str] = typer.Option('localhost', help='Host for the power monitor service.'),
        port: Optional[int] = typer.Option(6564, help='Port for the power monitor service.'),
):
    """Shows the status of the power monitor."""
    server_running(host=host, port=port)
    try:
        return requests.get(f'http://{host}:{port}').json()
    except requests.exceptions.ConnectionError:
        return False
