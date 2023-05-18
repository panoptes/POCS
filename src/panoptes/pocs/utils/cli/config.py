import subprocess
from pprint import pprint
from typing import Optional, Dict

import typer
from pydantic import BaseModel
from astropy import units as u

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


@app.command()
def setup():
    """Do initial setup of the config server"""
    # Clear the screen.
    subprocess.run('clear', shell=True)

    typer.echo(f'Setting up configuration for your PANOPTES unit.')
    # Make sure they want to proceed.
    proceed = typer.confirm('This will overwrite any existing configuration. Proceed?')
    if not proceed:
        typer.echo('Exiting.')
        raise typer.Abort()

    # Set the base directory.
    base_dir = typer.prompt('Enter the base directory for POCS', default='/home/panoptes/pocs')
    set_config('directories.base', base_dir)

    # Get the user-friendly name for the unit.
    unit_name = typer.prompt('Enter the user-friendly name for this unit', default=get_config('name'))
    set_config('name', unit_name)

    # Get the pan_id for the unit.
    pan_id = typer.prompt("Enter the PANOPTES ID for this unit. "
                          "If you don't have one yet just use the default.",
                          default=get_config('pan_id'))
    set_config('pan_id', pan_id)

    # Latitude
    latitude = typer.prompt('Enter the latitude for this unit, e.g. "19.5 deg"',
                            default=get_config('location.latitude'))
    set_config('location.latitude', str(u.Unit(latitude)))
    # Longitude
    longitude = typer.prompt('Enter the longitude for this unit, e.g. "-154.12 deg"',
                             default=get_config('location.longitude'))
    set_config('location.longitude', str(u.Unit(longitude)))
    # Elevation
    elevation = typer.prompt('Enter the elevation for this unit. '
                             'Use " ft" or " m" for units, e.g. "3400 m" or "12000 ft"',
                             default=get_config('location.elevation'))
    if ' ft' in elevation:
        elevation = (elevation.replace(' ft', '') * u.imperial.foot).to(u.meter)
    else:
        elevation = u.Unit(elevation)
    set_config('location.elevation', str(elevation))

    # Get timezone and then confirm if correct.
    timezone = subprocess.check_output('cat /etc/timezone', shell=True).decode().strip()
    timezone = typer.prompt('Enter the timezone for this unit', default=timezone)
    set_config('location.timezone', timezone)

    # Get GMT offset and then confirm if correct.
    gmt_offset = subprocess.check_output('date +%z', shell=True).decode().strip()
    # Convert GMT offset to minutes.
    gmt_offset = int(gmt_offset[:3]) * 60 + int(gmt_offset[-2:])
    gmt_offset = typer.prompt('Enter the GMT offset for this unit', default=gmt_offset)
    set_config('location.gmt_offset', gmt_offset)
    

@app.command()
def restart():
    """Restart the config server process via supervisorctl"""
    cmd = f'supervisorctl restart pocs-config-server'
    typer.echo(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
