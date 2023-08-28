import subprocess
from contextlib import suppress
from dataclasses import dataclass

import numpy as np
import requests
import typer
from rich import print

from sparklines import sparklines
from panoptes.pocs.utils.service.power import RelayCommand


@dataclass
class HostInfo:
    host: str = 'localhost'
    port: str = '6564'

    @property
    def url(self):
        return f'http://{self.host}:{self.port}'


app = typer.Typer()


@app.callback()
def common(context: typer.Context,
           host: str = typer.Option('localhost', help='Power monitor host address.'),
           port: str = typer.Option('6564', help='Power monitor port.'),
           ):
    context.obj = HostInfo(host=host, port=port)


@app.command()
def status(context: typer.Context):
    """Get the status of the power monitor."""
    url = context.obj.url
    try:
        res = requests.get(url)
        if res.ok:
            relays = res.json()
            for relay_index, relay_info in relays.items():
                with suppress(KeyError, TypeError):
                    relay_label = f'{relay_info["label"]:.<20s}'
                    print(f'[{relay_index}] '
                          f'{relay_label} [{"green" if relay_info["state"] == "ON" else "red"}]'
                          f'{relay_info["state"]}[/]')
        else:
            print(f'[red]{res.content.decode()}[/red]')
    except requests.exceptions.ConnectionError:
        print(f'[red]Cannot connect to {url}[/red]')


@app.command()
def readings(context: typer.Context):
    """Get the readings of the relays."""
    url = context.obj.url + '/readings'
    try:
        res = requests.get(url)
        if res.ok:
            relays = res.json()
            for relay_label, relay_readings in relays.items():
                relay_text = typer.style(f'{relay_label:.<20s}', fg=typer.colors.CYAN)
                relay_readings = [int(x) if int(x) >= 0 else 0 for x in relay_readings.values()]
                for val in sparklines(relay_readings):
                    print(f'{relay_text} {val} [{np.array(relay_readings).mean():.0f}]')
        else:
            print(f'[red]{res.content.decode()}[/red]')
    except requests.exceptions.ConnectionError:
        print(f'[red]Cannot connect to {url}[/red]')


@app.command()
def on(
        context: typer.Context,
        relay: str = typer.Argument(..., help='The label or index of the relay to turn on.'),
):
    """Turns a relay on."""
    control(context, relay=relay, command='turn_on')


@app.command()
def off(
        context: typer.Context,
        relay: str = typer.Argument(..., help='The label or index of the relay to turn off.'),
):
    """Turns a relay off."""
    control(context, relay=relay, command='turn_off')


@app.command()
def control(
        context: typer.Context,
        relay: str = typer.Option(..., help='The label or index of the relay to control.'),
        command: str = typer.Option(..., help='The control action to perform, '
                                              'either "turn_on" or "turn_off"')
):
    """Control a relay by label or relay index."""
    url = context.obj.url + '/control'

    try:
        relay_command = RelayCommand(relay=relay, command=command)
        res = requests.post(url, data=relay_command.json())
        content = res.json() if res.ok else res.content.decode()
        print(content)
    except requests.exceptions.ConnectionError:
        print(f'[red]Cannot connect to {url}')


@app.command()
def restart():
    """Restart the power server process via supervisorctl"""
    cmd = f'supervisorctl restart pocs-power-server'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
