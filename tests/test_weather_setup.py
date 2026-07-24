"""Tests for the remote weather station setup helpers in the weather CLI."""

import textwrap
from unittest.mock import MagicMock, patch

import requests
from rich.console import Console

from panoptes.pocs.utils.cli.weather import (
    _check_remote_weather_connection,
    _normalize_remote_url,
    _update_supervisord_for_remote,
)

# ---------------------------------------------------------------------------
# _normalize_remote_url
# ---------------------------------------------------------------------------


class TestNormalizeRemoteUrl:
    def test_plain_hostname_expands_to_full_url(self):
        assert _normalize_remote_url("PAN026") == "http://PAN026.local:6566/status"

    def test_plain_ip_address_expands_to_full_url(self):
        assert _normalize_remote_url("192.168.1.42") == "http://192.168.1.42:6566/status"

    def test_localhost_passed_through_without_local_suffix(self):
        assert _normalize_remote_url("localhost") == "http://localhost:6566/status"

    def test_http_url_returned_unchanged(self):
        url = "http://PAN026.local:6566/status"
        assert _normalize_remote_url(url) == url

    def test_https_url_returned_unchanged(self):
        url = "https://myweather.example.com/status"
        assert _normalize_remote_url(url) == url

    def test_http_url_with_different_port_returned_unchanged(self):
        url = "http://192.168.1.10:9999/weather"
        assert _normalize_remote_url(url) == url


# ---------------------------------------------------------------------------
# _check_remote_weather_connection
# ---------------------------------------------------------------------------


class TestCheckRemoteWeatherConnection:
    def _console(self):
        return Console(quiet=True)

    def test_returns_true_on_successful_json_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"is_safe": True}
        mock_response.raise_for_status.return_value = None

        with patch("panoptes.pocs.utils.cli.weather.requests.get", return_value=mock_response):
            result = _check_remote_weather_connection("http://PAN026.local:6566/status", self._console())

        assert result is True

    def test_returns_false_on_connection_error(self):
        with patch(
            "panoptes.pocs.utils.cli.weather.requests.get",
            side_effect=requests.exceptions.ConnectionError,
        ):
            result = _check_remote_weather_connection("http://PAN026.local:6566/status", self._console())

        assert result is False

    def test_returns_false_on_timeout(self):
        with patch(
            "panoptes.pocs.utils.cli.weather.requests.get",
            side_effect=requests.exceptions.Timeout,
        ):
            result = _check_remote_weather_connection("http://PAN026.local:6566/status", self._console())

        assert result is False

    def test_returns_false_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500")

        with patch("panoptes.pocs.utils.cli.weather.requests.get", return_value=mock_response):
            result = _check_remote_weather_connection("http://PAN026.local:6566/status", self._console())

        assert result is False

    def test_returns_false_on_invalid_json(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("No JSON")

        with patch("panoptes.pocs.utils.cli.weather.requests.get", return_value=mock_response):
            result = _check_remote_weather_connection("http://PAN026.local:6566/status", self._console())

        assert result is False


# ---------------------------------------------------------------------------
# _update_supervisord_for_remote
# ---------------------------------------------------------------------------


class TestUpdateSupervisordForRemote:
    _CONF_TEMPLATE = textwrap.dedent(
        """\
        [program:pocs-weather-reader]
        command=uvicorn --host 0.0.0.0 --port 6566 panoptes.pocs.utils.service.weather:app
        autostart=true
        stopasgroup=true

        [program:pocs-weather-reader-remote]
        command=pocs sensor monitor weather --read-frequency 90
        autostart=false
        stopasgroup=true
        """
    )

    def test_updates_autostart_values(self, tmp_path):
        conf_file = tmp_path / "conf_files" / "pocs-supervisord.conf"
        conf_file.parent.mkdir(parents=True)
        conf_file.write_text(self._CONF_TEMPLATE)

        console = Console(quiet=True)
        with patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_text.return_value = self._CONF_TEMPLATE
            written = []
            mock_path_instance.write_text.side_effect = written.append
            mock_path_cls.return_value = mock_path_instance

            _update_supervisord_for_remote(console)

        assert written, "write_text was never called"
        result = written[0]
        # Local reader should be disabled.
        assert "autostart=false" in result
        # Remote reader should be enabled — verify both values appear.
        lines = result.splitlines()
        autostart_values = [line.split("=", 1)[1] for line in lines if line.startswith("autostart=")]
        assert autostart_values.count("false") >= 1
        assert autostart_values.count("true") >= 1

    def test_no_write_when_conf_missing(self, tmp_path):
        console = Console(quiet=True)
        with patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path_cls.return_value = mock_path_instance

            _update_supervisord_for_remote(console)

        mock_path_instance.write_text.assert_not_called()

    def test_no_write_when_already_configured(self):
        local_section = (
            "[program:pocs-weather-reader]\n"
            "command=uvicorn --host 0.0.0.0 --port 6566 panoptes.pocs.utils.service.weather:app\n"
        )
        remote_section = (
            "[program:pocs-weather-reader-remote]\ncommand=pocs sensor monitor weather --read-frequency 90\n"
        )
        already_configured = self._CONF_TEMPLATE.replace(
            local_section + "autostart=true",
            local_section + "autostart=false",
        ).replace(
            remote_section + "autostart=false",
            remote_section + "autostart=true",
        )

        console = Console(quiet=True)
        with patch("panoptes.pocs.utils.cli.weather.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.read_text.return_value = already_configured
            mock_path_cls.return_value = mock_path_instance

            _update_supervisord_for_remote(console)

        mock_path_instance.write_text.assert_not_called()
