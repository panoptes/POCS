"""Tests for POCS telemetry service and Firestore hook."""

from __future__ import annotations

import builtins
import threading
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from panoptes.utils.telemetry.server import EventRequest, TelemetryService

from panoptes.pocs.utils.cli.telemetry import app as telemetry_cli_app
from panoptes.pocs.utils.service.telemetry import _get_unit_id, make_firestore_hook, make_pocs_telemetry_app

_REAL_IMPORT = builtins.__import__


def _raise_for_google(name, *args, **kwargs):
    """Side-effect for builtins.__import__ that blocks google.cloud.firestore."""
    if "google.cloud.firestore" in name or name == "google.cloud.firestore":
        raise ImportError(f"Mocked ImportError for {name}")
    return _REAL_IMPORT(name, *args, **kwargs)


@pytest.fixture
def unit_id():
    return "PAN001"


@pytest.fixture
def mock_firestore():
    """Patch google.cloud.firestore.Client and SERVER_TIMESTAMP for hook tests."""
    mock_client_cls = MagicMock()
    with (
        patch("google.cloud.firestore.Client", mock_client_cls),
        patch("google.cloud.firestore.SERVER_TIMESTAMP", "SERVER_TIMESTAMP"),
    ):
        yield mock_client_cls


class TestMakeFirestoreHook:
    def test_hook_uploads_on_store_permanently(self, unit_id, mock_firestore):
        """Hook should upload to Firestore when store_permanently=True."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref
        mock_firestore.return_value = mock_db

        hook = make_firestore_hook(unit_id=unit_id)

        envelope = {"type": "weather", "data": {"temp": 20.0}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="weather", data={"temp": 20.0}, store_permanently=True)
        hook(envelope, request)

        mock_db.document.assert_called_once_with(f"units/{unit_id}")
        mock_unit_ref.set.assert_called_once()
        mock_metadata_ref.add.assert_called_once()

    def test_hook_skips_ephemeral_events(self, unit_id, mock_firestore):
        """Hook must be a no-op when store_permanently=False."""
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db

        hook = make_firestore_hook(unit_id=unit_id)

        envelope = {"type": "power", "data": {}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="power", data={}, store_permanently=False)
        hook(envelope, request)

        mock_db.document.assert_not_called()

    def test_hook_sets_correct_firestore_paths(self, unit_id, mock_firestore):
        """Hook should write to units/{unit_id}/metadata collection."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref
        mock_firestore.return_value = mock_db

        hook = make_firestore_hook(unit_id=unit_id)

        envelope = {"type": "status", "data": {"cpu": 10}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="status", data={"cpu": 10}, store_permanently=True)
        hook(envelope, request)

        mock_db.document.assert_called_with(f"units/{unit_id}")
        mock_unit_ref.collection.assert_called_with("metadata")

    def test_hook_includes_timestamp_in_data(self, unit_id, mock_firestore):
        """Uploaded data should include 'date' from the envelope timestamp."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_metadata_ref = MagicMock()
        mock_db.document.return_value = mock_unit_ref
        mock_unit_ref.collection.return_value = mock_metadata_ref
        mock_firestore.return_value = mock_db

        hook = make_firestore_hook(unit_id=unit_id)
        ts = "2026-01-01T12:00:00.000Z"

        envelope = {"type": "weather", "data": {"temp": 15.0}, "ts": ts}
        request = EventRequest(type="weather", data={"temp": 15.0}, store_permanently=True)
        hook(envelope, request)

        added_data = mock_metadata_ref.add.call_args[0][0]
        assert added_data["date"] == ts
        assert added_data["record_type"] == "weather"

    def test_hook_exception_propagates_for_fire_hook(self, unit_id, mock_firestore):
        """Exceptions during hook invocation should propagate so TelemetryService can log them."""
        mock_db = MagicMock()
        mock_unit_ref = MagicMock()
        mock_unit_ref.set.side_effect = Exception("network error")
        mock_db.document.return_value = mock_unit_ref
        mock_firestore.return_value = mock_db

        hook = make_firestore_hook(unit_id=unit_id)

        envelope = {"type": "weather", "data": {}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="weather", data={}, store_permanently=True)
        with pytest.raises(Exception, match="network error"):
            hook(envelope, request)

    def test_hook_warns_and_returns_noop_when_google_not_installed(self, unit_id, caplog):
        """When google-cloud-firestore is missing, warn with install instructions and return a no-op."""
        import logging

        with patch("builtins.__import__", side_effect=_raise_for_google):
            with caplog.at_level(logging.WARNING):
                hook = make_firestore_hook(unit_id=unit_id)

        assert "google" in caplog.text.lower()

        # The returned hook must be a harmless no-op.
        envelope = {"type": "weather", "data": {}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="weather", data={}, store_permanently=True)
        hook(envelope, request)  # must not raise

    def test_hook_warns_and_returns_noop_when_client_creation_fails(self, unit_id, mock_firestore, caplog):
        """When firestore.Client() raises at hook-creation time, warn and return a no-op."""
        import logging

        mock_firestore.side_effect = Exception("no credentials")
        with caplog.at_level(logging.WARNING):
            hook = make_firestore_hook(unit_id=unit_id)

        assert "credentials" in caplog.text.lower()

        envelope = {"type": "weather", "data": {}, "ts": "2026-01-01T00:00:00Z"}
        request = EventRequest(type="weather", data={}, store_permanently=True)
        hook(envelope, request)  # must not raise

    def test_hook_non_fatal_via_telemetry_service(self, tmp_path):
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
        with patch("google.cloud.firestore.Client"), patch("google.cloud.firestore.SERVER_TIMESTAMP", "ts"):
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
        """Should query config store when UNIT_ID env var is absent."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.store.get_config", return_value="PAN099"):
            assert _get_unit_id() == "PAN099"

    def test_raises_when_no_unit_id(self, monkeypatch):
        """Should raise ValueError when neither env var nor config provides a unit id."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.store.get_config", return_value=None):
            with pytest.raises(ValueError, match="No unit id found"):
                _get_unit_id()

    def test_raises_when_config_unavailable(self, monkeypatch):
        """Should raise ValueError when config is unreachable."""
        monkeypatch.delenv("UNIT_ID", raising=False)
        with patch("panoptes.utils.config.store.get_config", side_effect=Exception("no config")):
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
                ["run", "--no-upload", "--site-dir", str(tmp_path), "--port", "16562"],
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
                    ["run", "--unit-id", "PAN001", "--no-upload", "--site-dir", str(tmp_path)],
                )
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        # Confirm --no-upload was respected (no Firestore hook registered).
        args, _ = mock_svc.call_args
        assert mock_svc.call_args.kwargs.get("post_event_hooks", []) == []


class TestCurrentTelemetryCli:
    def test_current_no_event_type(self):
        """current with no args delegates to panoptes-utils with host/port defaults."""
        runner = CliRunner()
        mock_proc = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = runner.invoke(telemetry_cli_app, ["current"])
        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["panoptes-utils", "telemetry", "current"]
        assert "--host" in cmd
        assert "--port" in cmd
        assert "--follow" not in cmd

    def test_current_with_event_type(self):
        """current <event_type> passes the event type as a positional arg."""
        runner = CliRunner()
        mock_proc = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = runner.invoke(telemetry_cli_app, ["current", "weather"])
        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert "weather" in cmd

    def test_current_follow_flag(self):
        """--follow is passed through to the subprocess command."""
        runner = CliRunner()
        mock_proc = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = runner.invoke(telemetry_cli_app, ["current", "--follow"])
        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert "--follow" in cmd

    def test_current_propagates_nonzero_exit_code(self):
        """A non-zero subprocess returncode is propagated as the CLI exit code."""
        runner = CliRunner()
        mock_proc = MagicMock(returncode=1)
        with patch("subprocess.run", return_value=mock_proc):
            result = runner.invoke(telemetry_cli_app, ["current"])
        assert result.exit_code == 1

    def test_current_custom_host_port(self):
        """--host and --port options are forwarded to the subprocess."""
        runner = CliRunner()
        mock_proc = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = runner.invoke(telemetry_cli_app, ["current", "--host", "192.168.1.10", "--port", "9999"])
        assert result.exit_code == 0, result.output
        cmd = mock_run.call_args[0][0]
        assert "192.168.1.10" in cmd
        assert "9999" in cmd
