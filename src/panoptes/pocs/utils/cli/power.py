from enum import Enum
from pprint import pprint
import requests
from panoptes.pocs.service.power import RelayAction

from panoptes.pocs.utils.logger import get_logger

import typer

app = typer.Typer()
state = {'verbose': False, 'host': 'http://localhost', 'port': 6564}
logger = get_logger(stderr_log_level='ERROR')


def server_running():
    """Check if the config server is running"""
    url = f'{state["host"]}{state["port"]}'

    is_running = False
    try:
        is_running = requests.get(url).ok
    except requests.exceptions.ConnectionError:
        run_status = typer.style('NOT RUNNING', fg=typer.colors.RED, bold=True)
        typer.secho(f'Server status: {run_status}')

    return is_running


@app.callback()
def main(ctx: typer.Context,
         host: str = typer.Option('http://localhost',
                                  help='Host of running power board server.'),
         port: int = typer.Option(6564,
                                  help='Port of running power board server.'),
         verbose: bool = False):
    state.update({
        'host': host,
        'port': port,
        'verbose': verbose,
    })
    if verbose:
        typer.echo(f'Command options: {state!r}')


@app.command()
def status():
    """Get the status of the power board."""
    if server_running():
        url = f'{state["host"]}{state["port"]}'
        res = requests.get(url)
        if res.ok:
            typer.secho(pprint(res.json()))
        else:
            run_status = typer.style('RUNNING', fg=typer.colors.RED, bold=True)
            typer.secho(f'Server status: {run_status}')
            typer.secho(f'Response: {res.content!r}')


@app.command()
def control(
        relay: str = typer.Argument(..., help='The name of the relay to control.'),
        action: RelayAction = typer.Argument(..., help='The action for the relay.'),
):
    """Control the relays on the power board."""
    if server_running():
        url = f'{state["host"]}{state["port"]}/relay/{relay}/control/{action}'
        res = requests.post(url)
        if res.ok:
            typer.secho(pprint(res.json()))


if __name__ == "__main__":
    app()
