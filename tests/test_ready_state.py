"""Tests for the ready state, particularly the smart day sleep timer."""

from astropy.time import Time
from unittest.mock import MagicMock, patch

from panoptes.pocs.state.states.default.ready import _calculate_wait_until_dark


def test_calculate_wait_until_dark_daytime():
    """Test that calculate_wait_until_dark returns appropriate wait time during day."""
    # Create a mock POCS object with necessary attributes
    mock_pocs = MagicMock()
    mock_observer = MagicMock()
    mock_pocs.observatory.observer = mock_observer

    # Set up a scenario where twilight is 6 hours away
    mock_now = Time("2024-01-15 12:00:00")  # Noon
    mock_twilight = Time("2024-01-15 18:00:00")  # 6pm twilight

    with patch("panoptes.pocs.state.states.default.ready.current_time", return_value=mock_now):
        mock_observer.twilight_evening_astronomical.return_value = mock_twilight

        wait_time = _calculate_wait_until_dark(mock_pocs)

        # Expected: 6 hours (21600s) minus 10 minute buffer (600s) = 21000s
        expected_wait = (6 * 3600) - (10 * 60)
        assert wait_time == expected_wait
        assert wait_time == 21000  # 5 hours 50 minutes


def test_calculate_wait_until_dark_near_twilight():
    """Test wait time when very close to twilight."""
    mock_pocs = MagicMock()
    mock_observer = MagicMock()
    mock_pocs.observatory.observer = mock_observer

    # Set up scenario where twilight is only 3 minutes away
    mock_now = Time("2024-01-15 17:57:00")
    mock_twilight = Time("2024-01-15 18:00:00")

    with patch("panoptes.pocs.state.states.default.ready.current_time", return_value=mock_now):
        mock_observer.twilight_evening_astronomical.return_value = mock_twilight

        wait_time = _calculate_wait_until_dark(mock_pocs)

        # Should return minimum wait time since we're close to twilight
        # (3 minutes - 10 minute buffer would be negative, so min_wait kicks in)
        min_wait = 5 * 60  # 5 minutes
        assert wait_time == min_wait


def test_calculate_wait_until_dark_far_future():
    """Test wait time calculation for early morning (many hours until evening)."""
    mock_pocs = MagicMock()
    mock_observer = MagicMock()
    mock_pocs.observatory.observer = mock_observer

    # Set up scenario where twilight is 14 hours away (early morning)
    mock_now = Time("2024-01-15 04:00:00")  # 4am
    mock_twilight = Time("2024-01-15 18:00:00")  # 6pm twilight

    with patch("panoptes.pocs.state.states.default.ready.current_time", return_value=mock_now):
        mock_observer.twilight_evening_astronomical.return_value = mock_twilight

        wait_time = _calculate_wait_until_dark(mock_pocs)

        # Expected: 14 hours minus 10 minute buffer
        expected_wait = (14 * 3600) - (10 * 60)
        assert wait_time == expected_wait
        # This should be a long sleep - more than 10 hours
        assert wait_time > 10 * 3600


def test_calculate_wait_until_dark_minimum_enforced():
    """Test that minimum wait time is enforced even with negative time calculations."""
    mock_pocs = MagicMock()
    mock_observer = MagicMock()
    mock_pocs.observatory.observer = mock_observer

    # Twilight is only 1 minute away
    mock_now = Time("2024-01-15 17:59:00")
    mock_twilight = Time("2024-01-15 18:00:00")

    with patch("panoptes.pocs.state.states.default.ready.current_time", return_value=mock_now):
        mock_observer.twilight_evening_astronomical.return_value = mock_twilight

        wait_time = _calculate_wait_until_dark(mock_pocs)

        # Should never be less than minimum wait time
        min_wait = 5 * 60
        assert wait_time >= min_wait


def test_calculate_wait_logs_info(caplog):
    """Test that the function logs appropriate information."""
    mock_pocs = MagicMock()
    mock_observer = MagicMock()
    mock_pocs.observatory.observer = mock_observer

    mock_now = Time("2024-01-15 12:00:00")
    mock_twilight = Time("2024-01-15 18:00:00")

    with patch("panoptes.pocs.state.states.default.ready.current_time", return_value=mock_now):
        mock_observer.twilight_evening_astronomical.return_value = mock_twilight

        _calculate_wait_until_dark(mock_pocs)

        # Verify the logger was called with appropriate message
        mock_pocs.logger.info.assert_called_once()
        call_args = mock_pocs.logger.info.call_args[0][0]
        assert "Daytime sleep" in call_args
        assert "21000" in call_args  # wait time in seconds
        assert "5.8h" in call_args  # wait time in hours
