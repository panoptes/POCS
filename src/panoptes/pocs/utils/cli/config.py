from pprint import pprint
from typing import Optional, Dict

import typer
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
        typer.secho(f'Server status: {run_status}')

    return is_running


@app.callback()
def main(context: typer.Context):
    context.params.update(context.parent.params)
    verbose = context.params['verbose']
    host_info['config_server'] = HostInfo(host=context.params['config_host'],
                                          port=context.params['config_port'],
                                          verbose=verbose)
    if verbose:
        typer.echo(f'Command options from power: {context.params!r}')


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
    """Get an item from the config"""
    if server_running():
        metadata = host_info['config_server']
        item = set_config(key, value, host=metadata.host, port=metadata.port)
        typer.secho(pprint(item), fg=typer.colors.MAGENTA)


if __name__ == "__main__":
    app()
