import typer

from panoptes.pocs.service import mount

app = typer.Typer()
app.add_typer(mount.app, name="mount")

if __name__ == "__main__":
    app()
