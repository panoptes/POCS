"""Typer CLI commands for the POCS telemetry server."""

from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

app = typer.Typer(no_args_is_help=True)


@app.command("run")
def run_telemetry_server(
    host: str = typer.Option("0.0.0.0", help="Host address to bind the telemetry server to."),
    port: int = typer.Option(6562, help="Port number to bind the telemetry server to."),
    site_dir: Path = typer.Option(Path("telemetry"), help="Directory for rotated NDJSON telemetry files."),
    unit_id: str = typer.Option(
        None, help="PANOPTES unit id for Firestore uploads. Defaults to UNIT_ID env var."
    ),
    no_upload: bool = typer.Option(False, "--no-upload", help="Disable Firestore uploads (local dev mode)."),
):
    """Run the POCS telemetry server with optional Firestore mirroring.

    This replaces the separate ``pocs-telemetry-server`` + ``pocs-metadata-uploader``
    supervisord processes with a single service.  Events marked
    ``store_permanently=True`` are mirrored to Firestore in a background thread
    unless ``--no-upload`` is given.

    Args:
        host: Bind address for the uvicorn server.
        port: TCP port for the uvicorn server.
        site_dir: Directory where rotated NDJSON telemetry files are written.
        unit_id: PANOPTES unit identifier for Firestore document paths.
        no_upload: When set, skip Firestore uploads (useful for local development
            without cloud credentials).
    """
    from panoptes.pocs.utils.service.telemetry import make_pocs_telemetry_app

    upload = not no_upload
    telemetry_app = make_pocs_telemetry_app(
        site_dir=site_dir,
        unit_id=unit_id,
        upload_to_firestore=upload,
    )

    typer.echo(f"Starting POCS telemetry server on {host}:{port} (site_dir={site_dir}, firestore={upload})")
    uvicorn.run(telemetry_app, host=host, port=port)
