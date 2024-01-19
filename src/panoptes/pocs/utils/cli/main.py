import typer

from panoptes.pocs.utils.cli import config
from panoptes.pocs.utils.cli import sensor
from panoptes.pocs.utils.cli import network
from panoptes.pocs.utils.cli import mount
from panoptes.pocs.utils.cli import camera
from panoptes.pocs.utils.cli import notebook
from panoptes.pocs.utils.cli import power
from panoptes.pocs.utils.cli import run
from panoptes.pocs.utils.cli import weather
from rich import print

app = typer.Typer()
state = {'verbose': False}

app.add_typer(config.app, name="config", help='Interact with the config server.')
app.add_typer(network.app, name="network", help='Interact with panoptes network.')
app.add_typer(mount.app, name="mount", help='Simple mount controls.')
app.add_typer(camera.app, name="camera", help='Simple camera controls.')
app.add_typer(notebook.app, name="notebook", help='Start Jupyter notebook environment.')
app.add_typer(power.app, name="power", help='Interact with power relays.')
app.add_typer(run.app, name="run", help='Run POCS!')
app.add_typer(sensor.app, name="sensor", help='Interact with system sensors.')
app.add_typer(weather.app, name="weather", help='Interact with weather station service.')


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
        print(f'Command options from main: {context.params!r}')


if __name__ == "__main__":
    app()
