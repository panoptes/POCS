from pprint import pprint
from typing import Dict, Optional

import requests
import typer
from pydantic import BaseModel
from panoptes.utils.config.client import get_config, set_config
from panoptes.pocs.utils.logger import get_logger
from panoptes.pocs.utils.service.power import RelayAction


class State(BaseModel):
    host: str = '127.0.0.1'
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


def get_status():
    metadata = state['metadata']
    res = requests.get(metadata.url)
    if res.ok:
        return res.json()
    else:
        run_status = typer.style('RUNNING', fg=typer.colors.RED, bold=True)
        typer.secho(f'Server status: {run_status}')
        typer.secho(f'Response: {res.content!r}')
        return None


@app.callback()
def main(context: typer.Context,
         host: str = typer.Option('http://127.0.0.1',
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
    power_status = get_status()
    if power_status is None:
        run_status = typer.style('RUNNING',
                                 fg=typer.colors.RED,
                                 bg=typer.colors.BLACK,
                                 bold=True)
        typer.secho(f'Server status: {run_status}')
    else:
        pprint(power_status)


@app.command()
def control(
        relay: str = typer.Argument(..., help='The name of the relay to control.'),
        action: RelayAction = typer.Argument(..., help='The action for the relay.'),
):
    """Control the relays on the power board."""
    metadata = state['metadata']
    url = f'{metadata.url}/relay/{relay}/control/{action}'
    res = requests.get(url)
    if res.ok:
        typer.secho(pprint(res.json()))


@app.command()
def setup_wizard(
        relay: str = typer.Option(None, min=0, max=4,
                                  help='The index number of a specific ray to configure. '
                                       'If not given, all relays will be configured.')
):
    power_config = get_config('environment.power.relays')
    if power_config is None:
        typer.secho(f'Power board does not appear to be running, cannot run wizard.')
        return

    typer.secho(f'* Setting up the power board config *',
                fg=typer.colors.BLACK,
                bg=typer.colors.RED,
                bold=True)

    for relay_name, relay_info in power_config.items():
        if relay is not None and f'RELAY_{relay}' != relay_name:
            typer.secho(f'Skipping {relay_name}')
            continue

        typer.secho('*' * 20, fg=typer.colors.YELLOW)
        typer.echo('Setting up: ' +
                   typer.style(relay_name, fg=typer.colors.GREEN) + ' ' +
                   typer.style(f'{relay_info!r}', fg=typer.colors.BLUE)
                   )
        if relay is None and typer.prompt(f'Edit?', default='no').lower().startswith('n'):
            continue

        if typer.prompt(f'Change relay state before editing?',
                        default='no').lower().startswith('y'):
            action = typer.prompt(f'Turn relay on or off?',
                                  default=RelayAction.turn_on,
                                  type=RelayAction,
                                  show_choices=True
                                  )
            try:
                res = requests.post('/control', data=dict(relay=relay_name, action=action))
                if res.ok is False:
                    raise Exception
            except Exception:
                typer.secho(f'Previous command failed. Check relay.',
                            fg=typer.colors.BLACK,
                            bg=typer.colors.RED,
                            bold=True)
                should_continue = typer.prompt('Do you want to continue? [yes/no]', type=bool)
                if should_continue is False:
                    return

        new_relay_label = typer.prompt(
            text=f'Enter label for {relay_name}.',
            default=relay_info['label'],
        )
        new_default_state = typer.prompt(
            text=f'Enter default state for {relay_name}.',
            default=relay_info['default_state'],
            type=str,
        )
        new_config = dict(label=new_relay_label, default_state=new_default_state)
        typer.secho(typer.style('New config: ', fg=typer.colors.RED) +
                    typer.style(f'{new_config!r}', fg=typer.colors.BRIGHT_BLUE))
        if typer.prompt('Set new config?', default='yes').lower().startswith('y'):
            set_config(f'environment.power.relays.{relay_name}.label', new_relay_label)
            set_config(f'environment.power.relays.{relay_name}.default_state', new_default_state)
            typer.secho('Config set', fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":
    app()
