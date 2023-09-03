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


@app.command(name='status')
def status(context: typer.Context):
    """Get the status of the weather station."""
    url = context.obj.url
    try:
        res = requests.get(url)
        if res.ok:
            return res.json()
        else:
            print(f'[red]{res.content.decode()}[/red]')
    except requests.exceptions.ConnectionError:
        print(f'[red]Cannot connect to {url}[/red]')


@app.command(name='readings')
def readings(context: typer.Context):
    """Get the weather readings."""
    url = context.obj.url + '/readings'
    try:
        res = requests.get(url)
        if res.ok:
            return res.json()
        else:
            print(f'[red]{res.content.decode()}[/red]')
    except requests.exceptions.ConnectionError:
        print(f'[red]Cannot connect to {url}[/red]')


@app.command()
def restart():
    """Restart the weather station service via supervisorctl"""
    cmd = f'supervisorctl restart pocs-weather-reader'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
