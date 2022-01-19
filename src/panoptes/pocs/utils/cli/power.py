from contextlib import suppress
from typing import Optional

import requests
import typer
from libtmux.exc import TmuxSessionExists

from panoptes.pocs.utils.cli.helpers import start_tmux_session, stop_tmux_session, server_running

app = typer.Typer()


@app.command()
def start(
        host: Optional[str] = typer.Option('localhost', help='Host for the power monitor service.'),
        port: Optional[int] = typer.Option(6564, help='Port for the power monitor service.'),
        session_name: Optional[str] = typer.Option('power-monitor',
                                                   help='Session name for the service.')
):
    """Starts the power monitor service."""

    cmd = 'uvicorn'
    options = f'--host {host} --port {port}'
    app_name = 'panoptes.pocs.utils.service.power:app'

    with suppress(TmuxSessionExists):
        start_tmux_session(session_name, f'{cmd} {options} {app_name}')
        typer.secho(f'Power Monitor session started on {host}:{port}')


@app.command()
def stop(
        session_name: Optional[str] = typer.Argument('power-monitor',
                                                     help='The name of the tmux session that '
                                                          'contains the running power monitor.')
):
    """Kills a running power monitor."""
    stop_tmux_session(session_name)


@app.command()
def turn_on(
        relay: str = typer.Option(..., help='The name of the relay to turn on.'),
        url: str = typer.Option('http://localhost:6564/control',
                                help='The url for the power monitor.')
):
    """Turns on a relay."""
    res = requests.post(url=url, data=dict(relay=relay, command='turn_on'))
    if res.ok:
        typer.secho(f'{relay} turned on.')


@app.command()
def turn_off(
        relay: str = typer.Option(..., help='The name of the relay to turn off.'),
        url: str = typer.Option('http://localhost:6564/control',
                                help='The url for the power monitor.')
):
    """Turns off a relay."""
    res = requests.post(url=url, data=dict(relay=relay, command='turn_off'))
    if res.ok:
        typer.secho(f'{relay} turned off.')


@app.command()
def status(
        relay: str = typer.Option(None,
                                  help='If None (the default), return the status for all relays, '
                                       'otherwise just the given.'),
        url: str = typer.Option('http://localhost:6564', help='The url for the power monitor.')
):
    """Turns on a relay."""
    res = requests.get(url=url, data=dict(relay=relay))
    if res.ok:
        return res.json()


@app.command()
def readings(
        relay: str = typer.Option(None,
                                  help='If None (the default), return the status for all relays, '
                                       'otherwise just the given.'),
        url: str = typer.Option('http://localhost:6564/readings',
                                help='The url for the power monitor.')
):
    """Get the power readings."""
    res = requests.post(url=url, data=dict(relay=relay))
    if res.ok:
        power_status = res.json()
        if relay in power_status:
            return power_status[relay]
        else:
            return power_status
