from typing import Optional

import libtmux
import typer
from libtmux.exc import TmuxSessionExists, LibTmuxException

app = typer.Typer()


@app.command()
def start(
        host: Optional[str] = typer.Option('localhost', help='Host for the power monitor service.'),
        port: Optional[str] = typer.Option(6564, help='Port for the power monitor service.'),
        session_name: Optional[str] = typer.Option('power-monitor',
                                                   help='Session name for the service.')
):
    """Starts the power monitor service."""
    server = libtmux.Server()

    try:
        session = server.new_session(session_name=session_name)
        pane0 = session.attached_pane

        cmd = 'uvicorn'
        options = f'--host {host} --port {port} panoptes.pocs.utils.service.power:app'

        pane0.send_keys(f'{cmd} {options}')
        typer.secho(f'Power Monitor session started on {host}:{port}')
    except TmuxSessionExists:
        typer.secho('Session exists for Power Monitor')


@app.command()
def stop(
        session_name: Optional[str] = typer.Argument('power-monitor',
                                                     help='The name of the tmux session that '
                                                          'contains the running power monitor.')
):
    """Kills a running power monitor."""
    server = libtmux.Server()
    try:
        server.kill_session(session_name)
    except LibTmuxException:
        typer.secho(f'No running Power Monitor')
