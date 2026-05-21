"""Tests for POCS telemetry service and Firestore hook."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from panoptes.utils.telemetry.server import EventRequest, TelemetryService

from panoptes.pocs.utils.service.telemetry import make_firestore_hook, make_pocs_telemetry_app


@pytest.fixture
def unit_id():
    return "PAN001"


class TestMakeFirestoreHook:
    def test_hook_uploads_on_store_permanently(self, unit_id, tmp_path):
        """Hook should upload to Firestore when store_permanently=True."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref

        hook = make_firestore_hook(unit_id=unit_id)

        with patch("google.cloud.firestore.Client", return_value=mock_db):
            envelope = {"type": "weather", "data": {"temp": 20.0}, "ts": "2026-01-01T00:00:00Z"}
            request = EventRequest(type="weather", data={"temp": 20.0}, store_permanently=True)
            hook(envelope, request)

        mock_db.document.assert_called_once_with(f"units/{unit_id}")
        mock_unit_ref.set.assert_called_once()
        mock_metadata_ref.add.assert_called_once()

    def test_hook_skips_ephemeral_events(self, unit_id):
        """Hook must be a no-op when store_permanently=False."""
        hook = make_firestore_hook(unit_id=unit_id)

        with patch("google.cloud.firestore.Client") as mock_client:
            envelope = {"type": "power", "data": {}, "ts": "2026-01-01T00:00:00Z"}
            request = EventRequest(type="power", data={}, store_permanently=False)
            hook(envelope, request)

        mock_client.assert_not_called()

    def test_hook_sets_correct_firestore_paths(self, unit_id, tmp_path):
        """Hook should write to units/{unit_id}/metadata collection."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref

        hook = make_firestore_hook(unit_id=unit_id)

        with patch("google.cloud.firestore.Client", return_value=mock_db):
            envelope = {"type": "status", "data": {"cpu": 10}, "ts": "2026-01-01T00:00:00Z"}
            request = EventRequest(type="status", data={"cpu": 10}, store_permanently=True)
            hook(envelope, request)

        mock_db.document.assert_called_with(f"units/{unit_id}")
        mock_unit_ref.collection.assert_called_with("metadata")

    def test_hook_includes_timestamp_in_data(self, unit_id):
        """Uploaded data should include 'date' from the envelope timestamp."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref

        hook = make_firestore_hook(unit_id=unit_id)
        ts = "2026-01-01T12:00:00.000Z"

        with patch("google.cloud.firestore.Client", return_value=mock_db):
            envelope = {"type": "weather", "data": {"temp": 15.0}, "ts": ts}
            request = EventRequest(type="weather", data={"temp": 15.0}, store_permanently=True)
            hook(envelope, request)

        added_data = mock_metadata_ref.add.call_args[0][0]
        assert added_data["date"] == ts
        assert added_data["record_type"] == "weather"

    def test_hook_exception_propagates_for_fire_hook(self, unit_id):
        """Exceptions in the hook should propagate so TelemetryService can log them."""
        hook = make_firestore_hook(unit_id=unit_id)

        with patch("google.cloud.firestore.Client", side_effect=Exception("no credentials")):
            envelope = {"type": "weather", "data": {}, "ts": "2026-01-01T00:00:00Z"}
            request = EventRequest(type="weather", data={}, store_permanently=True)
            with pytest.raises(Exception, match="no credentials"):
                hook(envelope, request)

    def test_hook_non_fatal_via_telemetry_service(self, unit_id, tmp_path):
        """When wired into TelemetryService, a Firestore failure must not affect the return value."""
        done = threading.Event()

        def failing_hook(envelope, request):
            done.set()
            raise RuntimeError("firestore down")

        service = TelemetryService(tmp_path / "site", post_event_hooks=[failing_hook])
        result = service.append_event(EventRequest(type="weather", data={"temp": 10}))

        assert done.wait(timeout=1.0), "hook was never called"
        assert result["seq"] == 1  # server returned normally despite hook failure


class TestMakePocsTelemetryApp:
    def test_returns_fastapi_app(self, tmp_path):
        """make_pocs_telemetry_app should return a FastAPI instance."""
        from fastapi import FastAPI

        app = make_pocs_telemetry_app(site_dir=tmp_path / "telemetry", upload_to_firestore=False)
        assert isinstance(app, FastAPI)

    def test_no_upload_registers_no_hooks(self, tmp_path):
        """With upload_to_firestore=False no hooks should be on the service."""
        app = make_pocs_telemetry_app(site_dir=tmp_path / "telemetry", upload_to_firestore=False)
        service = app.state.telemetry_service
        assert service._post_event_hooks == []

    def test_upload_registers_one_hook(self, tmp_path, unit_id):
        """With upload_to_firestore=True exactly one hook should be registered."""
        app = make_pocs_telemetry_app(
            site_dir=tmp_path / "telemetry",
            unit_id=unit_id,
            upload_to_firestore=True,
        )
        service = app.state.telemetry_service
        assert len(service._post_event_hooks) == 1
