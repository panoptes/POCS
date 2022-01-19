from contextlib import suppress
from typing import Optional

import libtmux
import requests
import typer
from libtmux.exc import LibTmuxException, TmuxSessionExists
from rich import print


def stop_tmux_session(session_name: str):
    """Stops the tmux session with the given name."""
    server = libtmux.Server()
    try:
        server.kill_session(session_name)
    except LibTmuxException:
        typer.secho(f'No running session named {session_name}')


def start_tmux_session(session_name: str, cmd: str):
    """Starts a tmux session and runs the cmd keys."""
    server = libtmux.Server()

    try:
        session = server.new_session(session_name=session_name)
        pane0 = session.attached_pane

        pane0.send_keys(cmd)
        typer.secho(f'{session_name} started.')
    except TmuxSessionExists:
        typer.secho(f'{session_name} already exists')


def is_tmux_session_running(session_name: str):
    """Simple check to see if tmux session exists"""
    server = libtmux.Server()
    try:
        session = server.find_where(dict(session_name=session_name))
        return True if session is not None else False
    except LibTmuxException:
        return False


def server_running(host: str = 'localhost', port: int = 6564, endpoint: str = '',
                   name: Optional[str] = None):
    """Check if the config server is running"""
    # NOTE: A bug in server_is_running means we cannot specify the port.
    is_running = False
    with suppress(requests.exceptions.ConnectionError):
        is_running = requests.get(f'http://{host}:{port}/{endpoint}').ok

    if is_running is None or is_running is False:
        run_status = '[bold red]:x: NOT RUNNING[/bold red]'
    else:
        run_status = '[bold green]:heavy_check_mark: RUNNING[/bold green]'

    service_name = f'{host}:{port}/{endpoint}' if name is None else name
    print(f'{service_name} status: {run_status}')

    return is_running
