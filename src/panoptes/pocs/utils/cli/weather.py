import subprocess

import requests
import typer
from rich import print

app = typer.Typer()


@app.command(name='status', help='Get the status of the weather station.')
def status(page='status', base_url='http://localhost:6566'):
    """Get the status of the weather station."""
    print(get_page(page, base_url))


@app.command(name='config', help='Get the configuration of the weather station.')
def config(page='config', base_url='http://localhost:6566'):
    """Get the configuration of the weather station."""
    print(get_page(page, base_url))


def get_page(page, base_url):
    url = f'{base_url}/{page}'
    return requests.get(url).json()


@app.command(help='Restart the weather station service via supervisorctl')
def restart(service: str = 'pocs-weather-reader'):
    """Restart the weather station service via supervisorctl"""
    cmd = f'supervisorctl restart {service}'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
