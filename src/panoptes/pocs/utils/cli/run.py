import typer
from rich import print
from typing_extensions import Annotated

from panoptes.pocs.core import POCS

app = typer.Typer()


@app.command(name='auto')
def run_auto(confirm: Annotated[bool, typer.Option(prompt=True)]) -> None:
    """Runs POCS automatically, like it's meant to be run."""
    print('Running POCS automatically!')

    if confirm is True:
        pocs = POCS.from_config()
        pocs.initialize()

        # Run the main loop
        try:
            pocs.run()
        except KeyboardInterrupt:
            print('POCS interrupted by user, shutting down.')
            print(f'[bold red]Please be patient, this may take a moment while the mount parks itself.[/bold red]]')
            pocs.power_down()
