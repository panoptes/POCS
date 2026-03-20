from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

import human_readable
import typer
from rich.panel import Panel
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Grid
from textual.widgets import Footer, Header, Static

from panoptes.utils.config.client import get_config
from panoptes.utils.telemetry import TelemetryClient

app = typer.Typer(no_args_is_help=True)


@app.command(name="run", help="Run the telemetry server.")
def run(
    host: str = typer.Option("localhost", help="Host address to bind the telemetry server to."),
    port: int = typer.Option(6562, help="Port number to bind the telemetry server to."),
    site_dir: str = typer.Option("telemetry", help="Directory for rotated site telemetry NDJSON files."),
    verbose: bool = typer.Option(False, help="Enable verbose logging."),
):
    """Run the telemetry server."""
    cmd = [
        "panoptes-utils",
        "telemetry",
        "run",
        "--host",
        host,
        "--port",
        str(port),
        "--site-dir",
        site_dir,
    ]
    if verbose:
        cmd.append("--verbose")
    subprocess.run(cmd)


@app.command(name="stop", help="Stop the telemetry server.")
def stop(
    host: str = typer.Option("localhost", help="Telemetry server host."),
    port: int = typer.Option(6562, help="Telemetry server port."),
):
    """Stop the telemetry server."""
    cmd = ["panoptes-utils", "telemetry", "stop", "--host", host, "--port", str(port)]
    subprocess.run(cmd)


@app.command(name="current", help="Display the current telemetry reading.")
def current(
    host: str = typer.Option("localhost", help="Telemetry server host."),
    port: int = typer.Option(6562, help="Telemetry server port."),
):
    """Display the current telemetry reading."""
    cmd = ["panoptes-utils", "telemetry", "current", "--host", host, "--port", str(port)]
    subprocess.run(cmd)


@app.command(name="tui", help="Start the telemetry TUI monitor.")
def tui(
    host: str = typer.Option("localhost", help="Telemetry server host."),
    port: int = typer.Option(6562, help="Telemetry server port."),
):
    """Start the telemetry TUI monitor."""
    run_tui(host=host, port=port)


class TelemetryDisplay(Static):
    """A widget to display telemetry data."""

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        """Update the display with new data.

        Args:
            data: The telemetry data.
            timestamp: The ISO-8601 timestamp from the event envelope.
        """
        raise NotImplementedError

    def get_footer(self, timestamp: str | None) -> str:
        """Get a human-readable footer with the last update time."""
        if not timestamp:
            return ""

        try:
            # The telemetry server uses UTC ISO-8601 with 'Z' suffix or +00:00.
            # We replace 'Z' with '+00:00' for fromisoformat if needed.
            ts_str = timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            now = datetime.now(dt.tzinfo)
            diff = now - dt
            return f"Updated {human_readable.date_time(diff)} ago"
        except Exception:
            return f"Updated {timestamp}"

    @staticmethod
    def get_val(data: dict[str, Any], key: str, default: Any = 0.0) -> Any:
        """Get a value from the data dictionary, falling back to default if None or missing."""
        val = data.get(key)
        return default if val is None else val


class WeatherDisplay(TelemetryDisplay):
    """Display weather telemetry."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.thresholds = get_config("weather.thresholds", default={})
        except Exception:
            self.thresholds = {}

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        if not data:
            self.update("No weather data")
            return

        # Try to fetch thresholds if not already loaded (e.g. if config server was down)
        if not self.thresholds:
            try:
                self.thresholds = get_config("weather.thresholds", default={})
            except Exception:
                pass

        is_safe = data.get("is_safe", False)
        safe_color = "green" if is_safe else "red"
        safe_text = "SAFE" if is_safe else "UNSAFE"

        table = Table(show_header=False, box=None, expand=True)
        table.add_row("Status", f"[{safe_color} bold]{safe_text}[/]")

        ambient_temp = self.get_val(data, "ambient_temp")
        sky_temp = self.get_val(data, "sky_temp")
        temp_diff = sky_temp - ambient_temp
        table.add_row("Ambient Temp", f"{ambient_temp:.1f} C")
        table.add_row("Sky Temp", f"{sky_temp:.1f} C")

        cloudy_threshold = self.thresholds.get("cloudy", "N/A")
        table.add_row("Sky - Ambient", f"{temp_diff:.1f} C [italic blue]({cloudy_threshold})[/]")

        wind_speed = self.get_val(data, "wind_speed")
        wind_threshold = self.thresholds.get("windy", "N/A")
        table.add_row("Wind Speed", f"{wind_speed:.1f} m/s [italic blue]({wind_threshold})[/]")

        for key in ["cloud", "wind", "rain"]:
            condition = data.get(f"{key}_condition", "Unknown")
            is_condition_safe = data.get(f"{key}_safe", False)
            color = "green" if is_condition_safe else "red"
            table.add_row(f"{key.title()} Status", f"[{color}]{condition}[/]")

        self.update(Panel(table, title="Weather", subtitle=self.get_footer(timestamp)))


class PowerDisplay(TelemetryDisplay):
    """Display power telemetry."""

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        if not data:
            self.update("No power data")
            return

        table = Table(show_header=False, box=None, expand=True)
        ac_ok = data.get("ac_ok")
        ac_color = "green" if ac_ok else "red"
        ac_text = "OK" if ac_ok else "OFF"
        table.add_row("AC Power", f"[{ac_color}]{ac_text}[/]")

        batt_low = data.get("battery_low")
        batt_color = "red" if batt_low else "green"
        batt_text = "LOW" if batt_low else "OK"
        table.add_row("Battery", f"[{batt_color}]{batt_text}[/]")

        table.add_row("Mount Amps", f"{self.get_val(data, 'mount'):.2f} A")
        table.add_row("Fans Amps", f"{self.get_val(data, 'fans'):.2f} A")
        table.add_row("Weather Amps", f"{self.get_val(data, 'weather_station'):.2f} A")

        self.update(Panel(table, title="Power", subtitle=self.get_footer(timestamp)))


class SafetyDisplay(TelemetryDisplay):
    """Display safety status."""

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        if not data:
            self.update("No safety data")
            return

        table = Table(show_header=False, box=None, expand=True)

        def get_bool_color(val):
            return "green" if val else "red"

        table.add_row("AC Power", f"[{get_bool_color(data.get('ac_power'))}]{data.get('ac_power')}[/]")
        table.add_row("Is Dark", f"[{get_bool_color(data.get('is_dark'))}]{data.get('is_dark')}[/]")
        table.add_row(
            "Good Weather", f"[{get_bool_color(data.get('good_weather'))}]{data.get('good_weather')}[/]"
        )
        table.add_row(
            "Free Space (Root)",
            f"[{get_bool_color(data.get('free_space_root'))}]{data.get('free_space_root')}[/]",
        )
        table.add_row(
            "Free Space (Images)",
            f"[{get_bool_color(data.get('free_space_images'))}]{data.get('free_space_images')}[/]",
        )

        self.update(Panel(table, title="Safety Status", subtitle=self.get_footer(timestamp)))


class StatusDisplay(TelemetryDisplay):
    """Display observatory status."""

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        if not data:
            self.update("No status data")
            return

        table = Table(show_header=False, box=None, expand=True)
        table.add_row("State", f"[bold yellow]{self.get_val(data, 'state', 'Unknown')}[/]")
        table.add_row("Next State", f"{self.get_val(data, 'next_state', 'None')}")
        table.add_row("Mount State", f"{self.get_val(data, 'mount_state', 'Unknown')}")
        table.add_row(
            "Mount RA/Dec",
            f"{self.get_val(data, 'mount_ra'):.2f} / {self.get_val(data, 'mount_dec'):.2f}",
        )
        table.add_row("Parked", f"{data.get('is_parked')}")
        table.add_row(
            "Sun/Moon Alt",
            f"{self.get_val(data, 'sun_alt'):.1f} / {self.get_val(data, 'moon_alt'):.1f}",
        )

        self.update(Panel(table, title="Observatory Status", subtitle=self.get_footer(timestamp)))


class ImageDisplay(TelemetryDisplay):
    """Display latest image metadata."""

    def update_data(self, data: dict[str, Any], timestamp: str | None = None) -> None:
        if not data:
            self.update("No image data")
            return

        table = Table(show_header=False, box=None, expand=True)
        table.add_row("Field", f"[bold cyan]{self.get_val(data, 'field_name', 'Unknown')}[/]")
        table.add_row("Camera", f"{self.get_val(data, 'camera_name', 'Unknown')}")
        table.add_row("Exp Time", f"{self.get_val(data, 'exptime'):.1f} s")
        table.add_row("Filter", f"{self.get_val(data, 'filter', 'Unknown')}")
        table.add_row("Start Time", f"{self.get_val(data, 'start_time', 'Unknown')}")
        table.add_row("Airmass", f"{self.get_val(data, 'airmass'):.2f}")

        self.update(Panel(table, title="Latest Image", subtitle=self.get_footer(timestamp)))


class TelemetryApp(App):
    """A Textual app to monitor telemetry."""

    CSS = """
    Grid {
        grid-size: 3 2;
        grid-gutter: 1;
        padding: 1;
    }
    #weather {
        column-span: 1;
    }
    #power {
        column-span: 1;
    }
    #safety {
        column-span: 1;
    }
    #status {
        column-span: 2;
    }
    #image {
        column-span: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, host: str = "localhost", port: int = 6562, **kwargs):
        super().__init__(**kwargs)
        self.client = TelemetryClient(host=host, port=port)

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            yield WeatherDisplay(id="weather")
            yield PowerDisplay(id="power")
            yield SafetyDisplay(id="safety")
            yield StatusDisplay(id="status")
            yield ImageDisplay(id="image")
        yield Footer()

    def on_mount(self) -> None:
        """Set up a timer to update the telemetry data."""
        self.update_telemetry()
        self.set_interval(1.0, self.update_telemetry)

    def update_telemetry(self) -> None:
        """Fetch latest telemetry and update widgets."""
        try:
            current_data = self.client.current().get("current", {})
        except Exception as e:
            # Show error in some way?
            self.notify(f"Error fetching telemetry: {e!r}", severity="error")
            return

        for widget_id in ["weather", "power", "safety", "status", "image"]:
            # Note: image type in telemetry is 'images'
            telemetry_type = "images" if widget_id == "image" else widget_id
            widget = self.query_one(f"#{widget_id}", TelemetryDisplay)
            event_envelope = current_data.get(telemetry_type, {})
            widget.update_data(event_envelope.get("data", {}), timestamp=event_envelope.get("ts"))

    def action_refresh(self) -> None:
        """Refresh the telemetry data manually."""
        self.update_telemetry()


def run_tui(host: str = "localhost", port: int = 6562):
    """Run the telemetry TUI."""
    app = TelemetryApp(host=host, port=port)
    app.run()
