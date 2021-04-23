from pprint import pprint
from typing import Dict, Optional

import requests
import typer
from panoptes.pocs.service.power import RelayAction
from panoptes.pocs.utils.logger import get_logger
from pydantic import BaseModel


class State(BaseModel):
    host: str = 'http://localhost'
    port: int = 6564
    verbose: bool = False

    @property
    def url(self):
        return f'{self.host}:{self.port}'


app = typer.Typer()
state: Dict[str, Optional[State]] = {'metadata': None}
logger = get_logger(stderr_log_level='ERROR')


def server_running():
    """Check if the config server is running"""
    metadata = state['metadata']

    is_running = False
    try:
        is_running = requests.get(metadata.url).ok
    except requests.exceptions.ConnectionError:
        run_status = typer.style('NOT RUNNING', fg=typer.colors.RED, bold=True)
        typer.secho(f'Server status: {run_status}')

    return is_running


@app.callback()
def main(context: typer.Context,
         host: str = typer.Option('http://localhost',
                                  help='Host of running power board server.'),
         port: int = typer.Option(6564,
                                  help='Port of running power board server.'),
         ):
    context.params.update(context.parent.params)
    verbose = context.params['verbose']
    state['metadata'] = State(host=host, port=port, verbose=verbose)
    if verbose:
        typer.echo(f'Command options from power: {context.params!r}')


@app.command()
def status():
    """Get the status of the power board."""
    if server_running():
        metadata = state['metadata']
        res = requests.get(metadata.url)
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
        metadata = state['metadata']
        url = f'{metadata.url}/relay/{relay}/control/{action}'
        res = requests.post(url)
        if res.ok:
            typer.secho(pprint(res.json()))


if __name__ == "__main__":
    app()
