import typer
from rich import print
from typing_extensions import Annotated

from panoptes.pocs.core import POCS

app = typer.Typer()


@app.command(name='auto')
def run_auto(confirm: Annotated[bool, typer.Option(prompt='Are you sure you want to run POCS automatically?')]) -> None:
    """Runs POCS automatically, like it's meant to be run."""

    if confirm is True:
        try:
            print('[green]Running POCS automatically!\tPress Ctrl-c to quit.[/green]')
            pocs = POCS.from_config()
            pocs.initialize()

            pocs.run()
        except KeyboardInterrupt:
            print('POCS interrupted by user, shutting down.')
            print(f'[bold red]Please be patient, this may take a moment while the mount parks itself.[/bold red]]')
            pocs.power_down()
        except Exception:
            print('[bold red]POCS encountered an error.[/bold red]')
