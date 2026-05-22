"""Tests for POCS telemetry service and Firestore hook."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from panoptes.utils.telemetry.server import EventRequest, TelemetryService

from panoptes.pocs.utils.cli.telemetry import app as telemetry_cli_app
from panoptes.pocs.utils.service.telemetry import _get_unit_id, make_firestore_hook, make_pocs_telemetry_app


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


class TestGetUnitId:
    def test_returns_env_var(self, monkeypatch):
        """Should return UNIT_ID env var when set."""
        monkeypatch.setenv("UNIT_ID", "PAN042")
        assert _get_unit_id() == "PAN042"

    def test_falls_back_to_config(self, monkeypatch):
        """Should query config server when UNIT_ID env var is absent."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.client.get_config", return_value="PAN099"):
            assert _get_unit_id() == "PAN099"

    def test_raises_when_no_unit_id(self, monkeypatch):
        """Should raise ValueError when neither env var nor config provides a unit id."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.client.get_config", return_value=None):
            with pytest.raises(ValueError, match="No unit id found"):
                _get_unit_id()

    def test_raises_when_config_unavailable(self, monkeypatch):
        """Should raise ValueError when config server is unreachable."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.client.get_config", side_effect=Exception("no server")):
            with pytest.raises(ValueError, match="No unit id found"):
                _get_unit_id()


class TestRunTelemetryServerCli:
    def test_run_no_upload(self, tmp_path, monkeypatch):
        """CLI --no-upload flag should start uvicorn without Firestore hooks."""
        runner = CliRunner()
        mock_run = MagicMock()
        monkeypatch.setenv("UNIT_ID", "PAN001")
        with patch("uvicorn.run", mock_run):
            result = runner.invoke(
                telemetry_cli_app,
                ["--no-upload", "--site-dir", str(tmp_path), "--port", "16562"],
            )
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 16562

    def test_run_with_unit_id(self, tmp_path):
        """CLI --unit-id flag should be passed through to make_pocs_telemetry_app."""
        runner = CliRunner()
        mock_run = MagicMock()
        with patch("uvicorn.run", mock_run):
            with patch("panoptes.pocs.utils.service.telemetry.TelemetryService") as mock_svc:
                mock_svc.return_value = MagicMock(_post_event_hooks=[])
                result = runner.invoke(
                    telemetry_cli_app,
                    ["--unit-id", "PAN001", "--no-upload", "--site-dir", str(tmp_path)],
                )
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        # Confirm --no-upload was respected (no Firestore hook registered).
        args, _ = mock_svc.call_args
        assert mock_svc.call_args.kwargs.get("post_event_hooks", []) == []
