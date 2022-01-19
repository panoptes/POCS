from contextlib import suppress
from pathlib import Path
from pprint import pprint
from typing import Optional, Dict

import typer
from libtmux.exc import TmuxSessionExists
from pydantic import BaseModel

from panoptes.pocs.utils.cli.helpers import stop_tmux_session, start_tmux_session, server_running
from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.config.client import get_config, set_config


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
def start(config_file: Path = typer.Argument(...,
                                             help='The YAML config file to use as the config.'),
          session_name: Optional[str] = typer.Option('config-server',
                                                     help='The name of the tmux session that '
                                                          'contains the running config server.')
          ):
    """Starts the config server."""
    host = host_info['config_server'].host
    port = host_info['config_server'].port

    cmd = 'panoptes-config-server'
    options = f'--host {host} --port {port} run --config-file {config_file}'

    with suppress(TmuxSessionExists):
        start_tmux_session(session_name, f'{cmd} {options}')
        typer.secho(f'Config Server session started on {host}:{port}')


@app.command()
def stop(
        session_name: Optional[str] = typer.Argument('config-server',
                                                     help='The name of the tmux session that '
                                                          'contains the running config server.')
):
    """Kills a running config server."""
    stop_tmux_session(session_name)


@app.command()
def status(
        host: Optional[str] = typer.Option('localhost', help='Host for the power monitor service.'),
        port: Optional[int] = typer.Option(6563, help='Port for the power monitor service.'),
        session_name: Optional[str] = typer.Option('config-server',
                                                   help='Session name for the service.')
):
    """Checks if config server is running."""
    return server_running(host, port, name=session_name, endpoint='/heartbeat')


@app.command(name='get')
def get_config_item(
        key: Optional[str] = typer.Argument(None,
                                            help='The key of the config item to get. '
                                                 'Can be specified in dotted-key notation '
                                                 'e.g. `directories.images`'),
        pretty_print: bool = typer.Option(True, help='Pretty print the display.'),
):
    """Get an item from the config server."""
    metadata = host_info['config_server']
    item = get_config(key, parse=pretty_print, host=metadata.host, port=metadata.port)
    if pretty_print:
        typer.echo(pprint(item))
    else:
        typer.echo(item)


@app.command(name='set')
def set_config_item(
        key: str = typer.Argument(...,
                                  help='The key, in dotted-notation, of the config item to get.'
                                       'A blank string (the default) will return the entire config.'),
        value: str = typer.Argument(..., help='The new value.')
):
    """Get an item from the config server."""
    metadata = host_info['config_server']
    item = set_config(key, value, host=metadata.host, port=metadata.port)
    typer.secho(pprint(item), fg=typer.colors.MAGENTA)


if __name__ == "__main__":
    app()
