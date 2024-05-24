import subprocess
from dataclasses import dataclass

import requests
import typer
from rich import print


@dataclass
class HostInfo:
    host: str = 'localhost'
    port: str = '6566'

    @property
    def url(self):
        return f'http://{self.host}:{self.port}'


app = typer.Typer()


@app.callback()
def common(context: typer.Context,
           host: str = typer.Option('localhost', help='Weather station host address.'),
           port: str = typer.Option('6566', help='Weather station port.'),
           ):
    context.obj = HostInfo(host=host, port=port)


@app.command(name='status', help='Get the status of the weather station.')
def status(context: typer.Context, page='status'):
    """Get the status of the weather station."""
    url = context.obj.url
    print(get_page(page, url))


@app.command(name='config', help='Get the configuration of the weather station.')
def config(context: typer.Context, page='config'):
    """Get the configuration of the weather station."""
    url = context.obj.url
    print(get_page(page, url))


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
