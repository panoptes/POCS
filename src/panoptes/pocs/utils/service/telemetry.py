"""POCS telemetry service with optional Firestore mirroring.

Provides ``make_firestore_hook`` to create a ``post_event_hook`` callback
that uploads permanently-stored telemetry events to Firestore, and
``make_pocs_telemetry_app`` to assemble the FastAPI app with that hook
already registered.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from panoptes.utils.telemetry.server import EventRequest, TelemetryService, create_app


def make_firestore_hook(unit_id: str | None = None):
    """Return a ``post_event_hook`` callable that mirrors events to Firestore.

    The hook only acts on events where ``request.store_permanently`` is
    ``True``, matching the previous behaviour of the watchdog-based metadata
    uploader.  All Firestore imports are deferred so the telemetry server
    can start even when the Google Cloud SDK is not installed or credentials
    are unavailable.

    Args:
        unit_id: PANOPTES unit identifier (e.g. ``"PAN001"``).  Falls back to
            the ``UNIT_ID`` environment variable, then the ``pan_id`` config
            key if not provided.

    Returns:
        A callable suitable for passing as an element of
        ``TelemetryService``'s ``post_event_hooks`` list.
    """
    resolved_unit_id = unit_id or _get_unit_id()

    def _hook(envelope: dict[str, Any], request: EventRequest) -> None:
        if not request.store_permanently:
            return

        try:
            from google.cloud import firestore  # deferred import

            db = firestore.Client()
            unit_ref = db.document(f"units/{resolved_unit_id}")
            metadata_records_ref = unit_ref.collection("metadata")

            record_type = envelope.get("type", "unknown")
            data: dict[str, Any] = dict(envelope.get("data") or {})
            data["date"] = envelope.get("ts")
            data["received_time"] = firestore.SERVER_TIMESTAMP

            unit_ref.set(
                {
                    "metadata": {record_type: data},
                    "last_updated": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )

            data["record_type"] = record_type
            metadata_records_ref.add(data)

            logger.debug(
                "Firestore hook: uploaded {record_type} for {unit_id}",
                record_type=record_type,
                unit_id=resolved_unit_id,
            )
        except Exception as exc:
            # Non-fatal: logged as warning by the TelemetryService hook runner,
            # but we also log here for clarity.
            logger.warning(
                "Firestore upload failed for unit {unit_id}: {exc!r}",
                unit_id=resolved_unit_id,
                exc=exc,
            )
            raise  # re-raise so TelemetryService logs via _fire_hook too

    return _hook


def make_pocs_telemetry_app(
    site_dir: str | Path = "telemetry",
    unit_id: str | None = None,
    upload_to_firestore: bool = True,
):
    """Create a FastAPI telemetry app with optional Firestore mirroring.

    Args:
        site_dir: Directory for rotated NDJSON telemetry files.
        unit_id: PANOPTES unit id for Firestore uploads.  If ``None``,
            resolved from the ``UNIT_ID`` env var or config.
        upload_to_firestore: When ``True`` (default), a Firestore hook is
            registered.  Pass ``False`` for local development without cloud
            credentials.

    Returns:
        A FastAPI application instance ready to be served with uvicorn.
    """
    hooks = [make_firestore_hook(unit_id)] if upload_to_firestore else []
    service = TelemetryService(site_dir=site_dir, post_event_hooks=hooks)
    return create_app(service)


def _get_unit_id() -> str:
    """Resolve the unit id from the environment or config server."""
    unit_id = os.getenv("UNIT_ID")
    if unit_id:
        return unit_id

    try:
        from panoptes.utils.config.client import get_config

        unit_id = get_config("pan_id")
    except Exception:
        pass

    if not unit_id:
        raise ValueError(
            "No unit id found. Set the UNIT_ID environment variable or ensure "
            "the config server is running with a 'pan_id' key."
        )

    return unit_id
