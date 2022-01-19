import typer
from rich.console import Console
from rich.table import Table
from enum import Enum

from panoptes.pocs.utils.cli import config
from panoptes.pocs.utils.cli import sensor
from panoptes.pocs.utils.cli import image
from panoptes.pocs.utils.cli import power
from panoptes.pocs.utils.cli import weather
from panoptes.pocs.utils.cli.helpers import is_tmux_session_running as is_running


class IsRunning(Enum):
    RUNNING = f'[bold green] Running [/bold green]'
    NOT_RUNNING = f'[bold red] Not running [/bold red]'


app = typer.Typer()
state = {'verbose': False, 'console': Console()}

app.add_typer(config.app, name="config", help='Interact with the config server.')
app.add_typer(sensor.app, name="sensor", help='Interact with system sensors.')
app.add_typer(image.app, name="image", help='Interact with images.')
app.add_typer(power.app, name="power", help='Interact with power system.')
app.add_typer(weather.app, name="weather", help='Interact with weather station.')


@app.callback()
def main(context: typer.Context,
         config_host: str = '127.0.0.1',
         config_port: int = 6563,
         verbose: bool = False):
    state.update({
        'config_host': config_host,
        'config_port': config_port,
        'verbose': verbose,
    })
    if verbose:
        typer.echo(f'Command options from main: {context.params!r}')


@app.command()
def status():
    """Shows POCS status."""
    console = state['console']

    status_table = Table()
    status_table.add_column('Service')
    status_table.add_column('Status', justify='right')

    sessions = ['config-server', 'power-monitor', 'weather-reader']
    for session in sessions:
        session_running = IsRunning.RUNNING if is_running(session) else IsRunning.NOT_RUNNING
        status_table.add_row(session.replace('-', ' ').title(), session_running.value)

    status_table.add_row('', '')
    status_table.add_row('POCS', 'N/A')

    console.print(status_table)


if __name__ == "__main__":
    app()
