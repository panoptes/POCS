import subprocess

import requests
import typer
from rich import print

app = typer.Typer()


@app.command(name='status', help='Get the status of the weather station.')
def status(url: str = 'http://localhost:6566'):
    """Get the status of the weather station."""
    print(requests.get(url).json())


@app.command(help='Restart the weather station service via supervisorctl')
def restart(serivce: str = 'pocs-weather-reader'):
    """Restart the weather station service via supervisorctl"""
    cmd = f'supervisorctl restart {serivce}'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
