from pprint import pprint
from typing import Optional

import requests.exceptions
from panoptes.pocs.utils.logger import get_logger

import typer

from panoptes.utils.config.client import get_config, set_config, server_is_running

app = typer.Typer()
state = {'verbose': False, 'host': 'http://localhost', 'port': 6563}
logger = get_logger(stderr_log_level='ERROR')


def server_running():
    """Check if the config server is running"""
    # NOTE: A bug in server_is_running means we cannot specify the port.
    is_running = server_is_running()
    if is_running is None or is_running is False:
        run_status = typer.style('NOT RUNNING', fg=typer.colors.RED, bold=True)
        typer.secho(f'Server status: {run_status}')

    return is_running


@app.callback()
def main(ctx: typer.Context,
         host: str = typer.Option('http://localhost', help='Host of running config server.'),
         port: int = typer.Option(6563, help='Port of running config server.'),
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
    server_running()


@app.command()
def get(
        key: Optional[str] = typer.Argument(None,
                                            help='The key of the config item to get. '
                                                 'Can be specified in dotted-key notation '
                                                 'e.g. `directories.images`'),
        pretty_print: bool = typer.Option(True, help='Pretty print the display.'),
):
    """Get an item from the config"""
    if server_running():
        item = get_config(key, parse=pretty_print)
        if pretty_print:
            typer.echo(pprint(item))
        else:
            typer.echo(item)


@app.command()
def set(
        key: str = typer.Argument(...,
                                  help='The key, in dotted-notation, of the config item to get.'
                                       'A blank string (the default) will return the entire config.'),
        value: str = typer.Argument(...,
                                    help='The new value. If none (the default), this will clear the entry.')
):
    """Get an item from the config"""
    if server_running():
        item = set_config(key, value, **state)
        typer.secho(pprint(item), fg=typer.colors.MAGENTA)


if __name__ == "__main__":
    app()
