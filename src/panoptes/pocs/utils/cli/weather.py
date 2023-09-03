import subprocess

import typer
from rich import print

from panoptes.utils.database import PanDB

app = typer.Typer()
DB = PanDB(db_type='file')


@app.command(name='status')
def status(context: typer.Context):
    """Get the status of the weather station."""
    return DB.get_current('weather')['data']


@app.command()
def restart():
    """Restart the weather station service via supervisorctl"""
    cmd = f'supervisorctl restart pocs-weather-reader'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
