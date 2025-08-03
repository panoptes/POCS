import human_readable
import requests
import subprocess
import typer
from dataclasses import dataclass
from datetime import datetime
from rich import print
from rich.console import Console
from rich.table import Table


@dataclass
class HostInfo:
    """Class to store and manage weather station host information.
    
    This class stores the host and port information for a weather station
    and provides a property to generate the complete URL.
    """
    host: str = 'localhost'
    port: str = '6566'

    @property
    def url(self):
        """Generate the complete URL for the weather station.
        
        Returns:
            str: The complete URL in the format 'http://{host}:{port}'
        """
        return f'http://{self.host}:{self.port}'


app = typer.Typer()


@app.callback()
def common(context: typer.Context,
           host: str = typer.Option('localhost', help='Weather station host address.'),
           port: str = typer.Option('6566', help='Weather station port.'),
           ):
    """Common callback for all commands in the weather CLI.
    
    This function sets up the context object with host information that will be
    available to all commands in the CLI application.
    
    Args:
        context: The Typer context object
        host: The hostname or IP address of the weather station
        port: The port number the weather station is listening on
    """
    context.obj = HostInfo(host=host, port=port)


@app.command(name='status', help='Get the status of the weather station.')
def status(context: typer.Context, page='status', show_raw_values: bool = False):
    """Get the status of the weather station.

    This command retrieves the latest weather data from the weather station and
    displays it in a formatted table on the command line. The table includes
    information about temperature, wind speed, cloud/wind/rain conditions, and
    their safety status.
    
    Args:
        context: The Typer context object containing the host information
        page: The API endpoint to query (defaults to 'status')
        show_raw_values: If True, prints the raw JSON data instead of a formatted table
        
    Returns:
        None: This function prints the weather data to the console
    """
    url = context.obj.url
    data = get_page(page, url)

    if isinstance(data, str) and data.startswith('No valid readings found'):
        print(f"[bold yellow]{data}[/bold yellow]")
        return

    if not show_raw_values:
        display_weather_table(data)


def display_weather_table(data: dict):
    """Display weather data in a formatted table.
    
    This function takes weather data in dictionary format and displays it in a
    nicely formatted table using the Rich library. The table includes information
    about temperatures, wind speed, and various safety conditions (cloud, wind, rain).
    The table is color-coded based on safety status (green for safe, red for unsafe).
    
    Args:
        data: A dictionary containing weather data with keys such as 'is_safe',
              'ambient_temp', 'sky_temp', 'wind_speed', 'cloud_condition',
              'wind_condition', 'rain_condition', 'timestamp', etc.
              
    Returns:
        None: This function prints the formatted table to the console
        
    Note:
        The table's title color is determined by the 'is_safe' value in the data.
        Individual rows for cloud, wind, and rain conditions are also color-coded
        based on their respective safety status.
    """
    # Create a Rich table
    is_safe = data['is_safe']
    table = Table(title="Weather Station Status", style='bold green' if is_safe else 'bold red')

    # Add columns for key and value
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Safety", style="green")

    # Show the sky and ambient temperature
    ambient_temp = data.get('ambient_temp')
    table.add_row('Ambient Temperature', f"{ambient_temp:>6.02f} C")

    sky_temp = data.get('sky_temp')
    table.add_row('Sky Temperature', f"{sky_temp:>6.02f} C")

    temp_diff = sky_temp - ambient_temp
    table.add_row("Sky - Ambient", f"{temp_diff:>6.02f} C")

    wind_speed = data.get('wind_speed')
    table.add_row('Wind Speed', f'{wind_speed:>6.02f} m/s')

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
    td0 = datetime.now() - time0
    formatted_time = f"{time0.isoformat(sep=' ', timespec='seconds')} - ({human_readable.date_time(td0)})"
    is_time_safe = str(td0.total_seconds() < 180)
    table.add_row('Time', formatted_time, is_time_safe, style='green' if is_time_safe else 'red')

    # Create a console and print the table
    console = Console()
    console.print(table)


@app.command(name='config', help='Get the configuration of the weather station.')
def config(context: typer.Context, page='config'):
    """Get the configuration of the weather station.
    
    This command retrieves the configuration settings from the weather station
    and prints them to the console in their raw JSON format.
    
    Args:
        context: The Typer context object containing the host information
        page: The API endpoint to query (defaults to 'config')
        
    Returns:
        None: This function prints the configuration data to the console
    """
    url = context.obj.url
    data = get_page(page, url)
    print(data)


def get_page(page, base_url):
    """Get JSON data from the specified page on the weather station.
    
    This function makes an HTTP request to the weather station API and returns
    the JSON response. It handles various error conditions that might occur
    during the request, providing helpful error messages and suggestions.
    
    Args:
        page: The endpoint to access (e.g., 'status', 'config')
        base_url: The base URL of the weather station
        
    Returns:
        dict: The parsed JSON data from the response
        
    Raises:
        SystemExit: If the request fails for any reason, with appropriate error
                   messages printed to the console before exiting
                   
    Note:
        This function has a timeout of 10 seconds for the HTTP request.
        If the request times out or fails, it will print a helpful error
        message with possible reasons and solutions before exiting.
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
    """Restart the weather station service via supervisorctl.
    
    This command uses the supervisorctl utility to restart the specified service.
    It's useful when the weather station service is not responding or needs to be
    refreshed after configuration changes.
    
    Args:
        service: The name of the service to restart (defaults to 'pocs-weather-reader')
        
    Returns:
        None: This function executes the restart command and prints the command being run
        
    Note:
        This command requires that supervisor is installed and configured on the system,
        and that the user has appropriate permissions to restart services.
    """
    cmd = f'supervisorctl restart {service}'
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True)


if __name__ == "__main__":
    app()
