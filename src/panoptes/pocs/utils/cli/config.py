from pathlib import Path
from pprint import pprint
from typing import Optional, Dict

import libtmux
import typer
from libtmux.exc import TmuxSessionExists, LibTmuxException
from pydantic import BaseModel

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config, set_config, server_is_running


class HostInfo(BaseModel):
    """Metadata for the Config Server"""
    host: str = '127.0.0.1'
    port: int = 6563
    verbose: bool = False

    @property
    def url(self):
        return f'{self.host}:{self.port}'


app = typer.Typer()
host_info: Dict[str, Optional[HostInfo]] = {'config_server': None}
logger = get_logger(stderr_log_level='ERROR')


def server_running():
    """Check if the config server is running"""
    # NOTE: A bug in server_is_running means we cannot specify the port.
    is_running = server_is_running()
    if is_running is None or is_running is False:
        run_status = typer.style('NOT RUNNING', fg=typer.colors.RED, bold=True)
        typer.secho(f'Config Server status: {run_status}')

    return is_running


@app.callback()
def main(context: typer.Context):
    context.params.update(context.parent.params)
    verbose = context.params['verbose']
    host_info['config_server'] = HostInfo(host=context.params['config_host'],
                                          port=context.params['config_port'],
                                          verbose=verbose)
    if verbose:
        typer.echo(f'Command options: {context.params!r}')


@app.command()
def start(config_file: Path = typer.Argument(None,
                                             help='The YAML config file to use as the config.'),
          session_name: Optional[str] = typer.Option('config-server',
                                                     help='The name of the tmux session that '
                                                          'contains the running config server.')
          ):
    """Starts the config server."""
    # Start tmux session
    server = libtmux.Server()

    host = host_info['config_server'].host
    port = host_info['config_server'].port

    try:
        session = server.new_session(session_name=session_name)
        pane0 = session.attached_pane

        cmd = 'panoptes-config-server'
        options = f'--host {host} --port {port} run --config-file {config_file}'

        pane0.send_keys(f'{cmd} {options}')
        typer.secho(f'Config Server session started on {host}:{port}')
    except TmuxSessionExists:
        typer.secho('Session exists for Config Server')


@app.command()
def stop(
        session_name: Optional[str] = typer.Argument('config-server',
                                                     help='The name of the tmux session that '
                                                          'contains the running config server.')
):
    """Kills a running config server."""
    server = libtmux.Server()
    try:
        server.kill_session(session_name)
    except LibTmuxException:
        typer.secho(f'No running Config Server')


@app.command()
def status():
    """Shows status of the config server."""
    server_running()


@app.command()
def get(
        key: Optional[str] = typer.Argument(None,
                                            help='The key of the config item to get. '
                                                 'Can be specified in dotted-key notation '
                                                 'e.g. `directories.images`'),
        pretty_print: bool = typer.Option(True, help='Pretty print the display.'),
):
    """Get an item from the config server."""
    if server_running():
        metadata = host_info['config_server']
        item = get_config(key, parse=pretty_print, host=metadata.host, port=metadata.port)
        if pretty_print:
            typer.echo(pprint(item))
        else:
            typer.echo(item)


@app.command()
def set(
        key: str = typer.Argument(...,
                                  help='The key, in dotted-notation, of the config item to get.'
                                       'A blank string (the default) will return the entire config.'),
        value: str = typer.Argument(..., help='The new value.')
):
    """Get an item from the config server."""
    if server_running():
        metadata = host_info['config_server']
        item = set_config(key, value, host=metadata.host, port=metadata.port)
        typer.secho(pprint(item), fg=typer.colors.MAGENTA)


if __name__ == "__main__":
    app()
