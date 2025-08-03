import human_readable
import requests
import subprocess
import typer
from dataclasses import dataclass
from datetime import datetime, timezone
from rich import print
from rich.console import Console
from rich.table import Table


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


def format_timestamp(timestamp):
    """Convert a timestamp to a human-friendly string.
    
    Args:
        timestamp: A timestamp string or number (assumed to be in seconds since epoch)
        
    Returns:
        A human-friendly string representation of the time difference
    """
    try:
        # Try to parse the timestamp as a float (seconds since epoch)
        timestamp_dt = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
    except (ValueError, TypeError):
        # If parsing fails, return the original timestamp
        return str(timestamp)

    now = datetime.now(tz=timezone.utc)
    diff = now - timestamp_dt

    # Calculate the time difference in various units
    seconds = diff.total_seconds()
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24

    # Format the time difference as a human-friendly string
    if days >= 2:
        return f"Over {int(days)} days old"
    elif days >= 1:
        return f"About {int(days)} day old"
    elif hours >= 1:
        return f"About {int(hours)} hours old"
    elif minutes >= 1:
        return f"About {int(minutes)} minutes old"
    else:
        return "Less than a minute old"


@app.command(name='status', help='Get the status of the weather station.')
def status(context: typer.Context, page='status'):
    """Get the status of the weather station.

    This command will read the lastest weather entry and generate a summary
    table for the command line.

        "ambient_temp": 13.583,
        "sky_temp": 8.957,
        "wind_speed": 0.0,
        "rain_frequency": 5225.0,
        "pwm": 0.0,
        "is_safe": False


    """
    url = context.obj.url
    data = get_page(page, url)
    display_weather_table(data)


def display_weather_table(data: dict):
    # Create a Rich table
    is_safe = data['is_safe']
    table = Table(title="Weather Station Status", style='bold green' if is_safe else 'bold red')

    # Add columns for key and value
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Safety", style="green")

    # Show the sky and ambient temperature
    ambient_temp = data.get('ambient_temp')
    table.add_row('Ambient Temperature', f"{ambient_temp:>5.02f} C")

    sky_temp = data.get('sky_temp')
    table.add_row('Sky Temperature', f"{sky_temp:>5.02f} C")

    temp_diff = sky_temp - ambient_temp
    table.add_row("Sky - Ambient", f"{temp_diff:>5.02f} C")

    wind_speed = data.get('wind_speed')
    table.add_row('Wind Speed', f'{wind_speed:>5.02f} m/s')

    # Get the cloud, wind, and rain conditions.

    for key in ['cloud', 'wind', 'rain']:
        condition = data.get(f"{key}_condition")
        condition_is_safe = data.get(f"{key}_safe")
        table.add_row(
            key.title(), condition.title(), str(condition_is_safe),
            style='green' if condition_is_safe else 'red'
        )

    # Get the timestamp and format so it's readable.
    time0 = datetime.fromisoformat(data.get('timestamp'))
    td0 = time0 - datetime.now()
    formatted_time = f"{time0.isoformat(sep=' ', timespec='seconds')} - ({human_readable.date_time(td0)})"
    is_time_safe = str(td0.total_seconds() < 180)
    table.add_row('Time', formatted_time, is_time_safe)

    # Create a console and print the table
    console = Console()
    console.print(table)


@app.command(name='config', help='Get the configuration of the weather station.')
def config(context: typer.Context, page='config'):
    """Get the configuration of the weather station."""
    url = context.obj.url
    data = get_page(page, url)
    print(data)


def get_page(page, base_url):
    """Get JSON data from the specified page on the weather station.
    
    Args:
        page: The endpoint to access (e.g., 'status', 'config')
        base_url: The base URL of the weather station
        
    Returns:
        The JSON data from the response
        
    Raises:
        SystemExit: If the request fails for any reason
    """
    url = f'{base_url}/{page}'
    console = Console()

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.ConnectionError:
        console.print(f"[bold red]Error:[/bold red] Could not connect to the weather station at [bold]{url}[/bold]")
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is not running")
        console.print("  • The host or port is incorrect")
        console.print("  • Network connectivity issues")
        console.print("\n[green]Try:[/green]")
        console.print(
            f"  • Running [bold]supervisorctl status pocs-weather-reader[/bold] to check if the service is running"
        )
        console.print(f"  • Running [bold]weather restart[/bold] to restart the weather service")
        console.print(f"  • Checking your network connection")
        exit(1)
    except requests.exceptions.Timeout:
        console.print(f"[bold red]Error:[/bold red] Request to [bold]{url}[/bold] timed out")
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is overloaded")
        console.print("  • Network connectivity issues")
        console.print("\n[green]Try:[/green]")
        console.print(f"  • Running [bold]weather restart[/bold] to restart the weather service")
        console.print(f"  • Trying again later")
        exit(1)
    except requests.exceptions.HTTPError as e:
        console.print(f"[bold red]Error:[/bold red] HTTP error occurred: [bold]{e}[/bold]")
        console.print(f"  URL: [bold]{url}[/bold]")
        exit(1)
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Error:[/bold red] An unexpected error occurred: [bold]{e}[/bold]")
        console.print(f"  URL: [bold]{url}[/bold]")
        exit(1)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] Invalid JSON response from [bold]{url}[/bold]")
        console.print("[yellow]Possible reasons:[/yellow]")
        console.print("  • The weather station service is not functioning correctly")
        console.print("  • The response format has changed")
        console.print("\n[green]Try:[/green]")
        console.print(f"  • Running [bold]weather restart[/bold] to restart the weather service")
        exit(1)


@app.command(help='Restart the weather station service via supervisorctl')
def restart(service: str = 'pocs-weather-reader'):
    """Restart the weather station service via supervisorctl"""
    cmd = f'supervisorctl restart {service}'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
