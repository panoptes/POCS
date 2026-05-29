"""CLI command for launching the POCS terminal UI."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
def launch(
    context: typer.Context,
    simulator: list[str] = typer.Option(None, "--simulator", "-s", help="Simulators to load"),
    no_pocs: bool = typer.Option(
        False,
        "--no-pocs",
        help="Launch TUI without starting POCS (monitor-only mode)",
    ),
) -> None:
    """Launch the POCS terminal dashboard.

    Starts an interactive curses TUI that provides live observatory status and
    full control over POCS operations. By default a POCS instance is created
    in-process from the current config file. Use ``--no-pocs`` for a read-only
    monitoring session against an already-running POCS.

    Args:
        context: Typer context.
        simulator: Simulators to enable (for example ``--simulator mount``).
        no_pocs: If True, launch in monitor-only mode without creating POCS.
    """
    del context
    from panoptes.utils.utils import listify

    from panoptes.pocs.tui.__main__ import curses_main

    pocs = None
    if not no_pocs:
        try:
            from panoptes.pocs.core import POCS

            simulators = listify(simulator) if simulator else None
            pocs = POCS.from_config(simulators=simulators)
        except Exception as err:
            typer.echo(f"Warning: could not create POCS instance: {err}", err=True)
            typer.echo("Launching in monitor-only mode.", err=True)

    curses_main(pocs=pocs)
