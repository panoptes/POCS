from typing import Optional

import typer
import requests

app = typer.Typer()


@app.command()
def status(
        host: Optional[str] = typer.Option('localhost', help='Host for the weather service.'),
        port: Optional[int] = typer.Option(6564, help='Port for the weather service.'),
        endpoint: Optional[str] = typer.Option('/current',
                                               help='The endpoint for the weather service.')
):
    """Shows the status of the power monitor."""
    try:
        return requests.get(f'http://{host}:{port}/{endpoint}').json()
    except requests.exceptions.ConnectionError:
        return False
