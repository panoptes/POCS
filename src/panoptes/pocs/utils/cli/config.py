"""Typer CLI helpers for interacting with the PANOPTES config file."""

import datetime
import os
from pathlib import Path

import typer
from astropy import units as u
from loguru import logger as _loguru_logger
from rich import print, prompt
from rich.console import Console
from rich.table import Table

from panoptes.utils.config import DEFAULT_CONFIG_PATH
from panoptes.utils.config import store as config_store
from panoptes.utils.config.helpers import save_config

from panoptes.pocs.utils.logger import get_logger

app = typer.Typer(no_args_is_help=True)
logger = get_logger(stderr_log_level="ERROR")


def _resolve_config_path() -> Path:
    """Return the config file path using the same resolution order as the store.

    Checks the store's already-resolved path first (set by init_config or tests),
    then falls back to $PANOPTES_CONFIG_FILE and the default location.
    """
    if config_store._CONFIG_FILE is not None:
        return config_store._CONFIG_FILE
    env = os.environ.get("PANOPTES_CONFIG_FILE")
    return Path(env).expanduser() if env else DEFAULT_CONFIG_PATH


def _require_config() -> None:
    """Exit with a friendly message when no config file can be found."""
    path = _resolve_config_path()
    if not path.exists():
        print(
            f"[red]No config file found at {path}.[/red]\nRun [bold]pocs config setup[/bold] to create one."
        )
        raise typer.Exit(code=1)


@app.command()
def status():
    """Print a summary of the current config file."""
    _require_config()
    path = _resolve_config_path()
    console = Console()
    try:
        cfg = config_store.get_config()
    except Exception as e:
        print(f"[red]Config error:[/red] {e}\nRun [bold]pocs config setup[/bold] to fix.")
        raise typer.Exit(code=1)

    loc = cfg.get("location", {})
    dirs = cfg.get("directories", {})

    def _count_keys(d: dict) -> int:
        """Recursively count all leaf keys in a nested dict."""
        total = 0
        for v in d.values():
            if isinstance(v, dict):
                total += _count_keys(v)
            else:
                total += 1
        return total

    stat = Table.grid(padding=(0, 2))
    stat.add_column(style="bold cyan", justify="right")
    stat.add_column()

    stat.add_row("Config file", str(path))
    mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    stat.add_row("Last edited", mtime)

    stat.add_row("Top-level keys", str(len(cfg)))
    stat.add_row("Total keys", str(_count_keys(cfg)))
    stat.add_row("", "")
    stat.add_row("PAN ID", str(cfg.get("pan_id", "[dim]—[/dim]")))
    stat.add_row("Unit name", str(cfg.get("name", "[dim]—[/dim]")))

    if loc:
        stat.add_row("Location", str(loc.get("name", "[dim]—[/dim]")))
        stat.add_row("Latitude", str(loc.get("latitude", "[dim]—[/dim]")))
        stat.add_row("Longitude", str(loc.get("longitude", "[dim]—[/dim]")))
        stat.add_row("Elevation", str(loc.get("elevation", "[dim]—[/dim]")))
        stat.add_row("Timezone", str(loc.get("timezone", "[dim]—[/dim]")))

    if dirs:
        stat.add_row("Base dir", str(dirs.get("base", "[dim]—[/dim]")))

    console.print("\n[green]✓ Config is ready[/green]\n")
    console.print(stat)
    console.print()


@app.command(name="get")
def get_value(
    key: str | None = typer.Argument(
        None,
        help="The key of the config item to get. "
        "Can be specified in dotted-key notation "
        "e.g. `directories.images`",
    ),
    parse: bool = typer.Option(True, help="Parse the item."),
):
    """Get an item from the config."""
    del parse
    _require_config()
    try:
        item = config_store.get_config(key)
    except Exception as e:
        print(f"[red]Config error:[/red] {e}\nRun [bold]pocs config setup[/bold] to fix.")
        raise typer.Exit(code=1)

    if isinstance(item, (dict, list)):
        from rich.syntax import Syntax

        from panoptes.utils.serializers import to_yaml

        yaml_str = to_yaml(item)
        Console().print(Syntax(yaml_str, "yaml", theme="ansi_dark", word_wrap=True))
    else:
        print(item)


@app.command(name="set")
def set_value(
    key: str = typer.Argument(
        ...,
        help="The key, in dotted-notation, of the config item to get."
        "A blank string (the default) will return the entire config.",
    ),
    value: str = typer.Argument(..., help="The new value."),
):
    """Set an item in the config."""
    if value.startswith(r"\-"):
        value = value[1:]
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            print(f"{value=} is not a number.")
    print(f"{type(value)=} {value=}")
    item = config_store.set_config(key, value)
    print(item)


@app.command()
def setup(
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write the config file. Defaults to $PANOPTES_CONFIG_FILE or ~/.panoptes/config.yaml.",
    ),
    merge_from: str = typer.Option(
        None,
        "--from",
        help=(
            "Path to an existing config file to use as a base. "
            "If not given, conf_files/pocs.yaml in the current directory is used if present."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip the overwrite confirmation prompt.",
    ),
):
    """Do initial setup of the config file."""
    # Suppress all log output during the interactive wizard.
    _loguru_logger.remove()

    console = Console()
    console.clear()

    print("Setting up configuration for your PANOPTES unit.")

    cwd = Path(os.getcwd())

    # Auto-detect conf_files/pocs.yaml relative to cwd when --from is not specified.
    if merge_from is None:
        default_from = cwd / "conf_files" / "pocs.yaml"
        if default_from.exists():
            use_base = prompt.Confirm.ask(
                f"Found [bold]{default_from.relative_to(cwd)}[/bold] — use it as a base configuration?",
                default=True,
            )
            if use_base:
                merge_from = str(default_from)

    # Load base config from file (if provided) into a plain dict so the config
    # store's lazy-init logic never fires during the wizard.
    cfg: dict = {}
    if merge_from:
        merge_from_path = Path(merge_from)
        if not merge_from_path.exists():
            print(f"[red]Config file not found:[/red] {merge_from}")
            raise typer.Exit(code=1)
        from panoptes.utils.serializers import from_yaml

        cfg = from_yaml(merge_from_path.read_text()) or {}
        print(f"[dim]Loaded base config from {merge_from}[/dim]")

    if output:
        print(f"Config will be saved to: [bold]{output}[/bold]")

    if not force:
        proceed = prompt.Confirm.ask(
            "This will overwrite any existing configuration. Proceed?", default=False
        )
        if not proceed:
            print("Exiting.")
            return

    def _get(key: str):
        """Get a dotted-key value from the local cfg dict."""
        val = cfg
        for part in key.split("."):
            if not isinstance(val, dict):
                return None
            val = val.get(part)
        return val

    def _set(key: str, value) -> None:
        """Set a dotted-key value in the local cfg dict."""
        parts = key.split(".")
        d = cfg
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value

    base_dir = prompt.Prompt.ask("Enter the base directory for POCS", default=str(cwd))
    _set("directories.base", base_dir)

    unit_name = prompt.Prompt.ask("Enter the user-friendly name for this unit", default=_get("name"))
    _set("name", unit_name)

    pan_id = prompt.Prompt.ask(
        "Enter the PANOPTES ID for this unit (use the default if you don't have one yet)",
        default=_get("pan_id"),
    )
    _set("pan_id", pan_id)

    _lat = _get("location.latitude")
    latitude = prompt.Prompt.ask(
        'Enter the latitude for this unit (e.g. "19.5 deg")',
        default=str(_lat) if _lat is not None else None,
    )
    if latitude is not None:
        _set("location.latitude", str(u.Quantity(latitude)))

    _lon = _get("location.longitude")
    longitude = prompt.Prompt.ask(
        'Enter the longitude for this unit (e.g. "-154.12 deg")',
        default=str(_lon) if _lon is not None else None,
    )
    if longitude is not None:
        _set("location.longitude", str(u.Quantity(longitude)))

    _elev = _get("location.elevation")
    elevation = prompt.Prompt.ask(
        'Enter the elevation for this unit (e.g. "3400 m" or "12000 ft")',
        default=str(_elev) if _elev is not None else None,
    )
    if elevation is not None:
        if " ft" in elevation:
            elevation = str((float(elevation.replace(" ft", "")) * u.imperial.foot).to(u.meter))
        _set("location.elevation", elevation)

    # Detect local timezone from the /etc/localtime symlink (macOS and Linux, no subprocess needed).
    timezone = _get("location.timezone") or "UTC"
    try:
        tz_link = os.readlink("/etc/localtime")
        timezone = tz_link.split("zoneinfo/", 1)[-1]
    except OSError:
        pass

    timezone = prompt.Prompt.ask("Enter the timezone for this unit", default=timezone)
    _set("location.timezone", timezone)

    gmt_offset = int(datetime.datetime.now().astimezone().utcoffset().total_seconds() / 60)
    gmt_offset_str = prompt.Prompt.ask(
        "Enter the GMT offset for this unit in minutes (e.g. 60 for 1 hour ahead, -120 for 2 hours behind)",
        default=str(_get("location.gmt_offset") or gmt_offset),
    )
    _set("location.gmt_offset", int(gmt_offset_str))

    save_config(save_path=output, config=cfg)
    saved_to = output or os.environ.get("PANOPTES_CONFIG_FILE", "~/.panoptes/config.yaml")
    print(f"[green]Config saved to {saved_to}.[/green]")


if __name__ == "__main__":
    app()
