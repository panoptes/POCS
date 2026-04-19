"""Tests for housekeeping state with nightly report generation."""
import pytest
from pathlib import Path
from collections import OrderedDict

from panoptes.pocs.state.states.default import housekeeping
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.scheduler.field import Field
from panoptes.utils.database import PanDB


@pytest.fixture
def db():
    """Create a test database instance."""
    return PanDB(db_type="memory", db_name="test_housekeeping")


class MockEventData:
    """Mock event data for state testing."""
    def __init__(self, pocs):
        self.model = pocs


class MockScheduler:
    """Mock scheduler for testing."""
    def __init__(self):
        self.observed_list = OrderedDict()
    
    def reset_observed_list(self):
        """Reset the observed list."""
        self.observed_list = OrderedDict()


class MockObservatory:
    """Mock observatory for testing."""
    def __init__(self):
        self.scheduler = MockScheduler()


class MockLogger:
    """Mock logger for testing."""
    def info(self, message):
        pass
    
    def warning(self, message):
        pass
    
    def debug(self, message):
        pass


class MockPOCS:
    """Mock POCS instance for testing."""
    def __init__(self, db, config_dir):
        self.db = db
        self.observatory = MockObservatory()
        self.next_state = None
        self._config_dir = config_dir
        self.messages = []
        self.logger = MockLogger()
        
    def say(self, message):
        """Record messages."""
        self.messages.append(message)
        
    def get_config(self, key, default=None):
        """Get config value."""
        if key == "directories.reports":
            return self._config_dir / "reports"
        return default


def test_housekeeping_generates_report(db, tmp_path):
    """Test that housekeeping state generates a nightly report."""
    # Create a mock POCS instance
    pocs = MockPOCS(db=db, config_dir=tmp_path)
    
    # Add some observations to the scheduler
    field = Field(name="Test Field", position="20h00m00s +30d00m00s")
    obs = Observation(field=field, exptime=120, min_nexp=10)
    obs.seq_time = "2026-02-13T01:00:00"
    pocs.observatory.scheduler.observed_list[obs.seq_time] = obs
    
    # Create mock event data
    event_data = MockEventData(pocs)
    
    # Call housekeeping on_enter
    housekeeping.on_enter(event_data)
    
    # Check that next_state was set
    assert pocs.next_state == "sleeping"
    
    # Check that observed_list was reset
    assert len(pocs.observatory.scheduler.observed_list) == 0
    
    # Check that report file was created
    reports_dir = tmp_path / "reports"
    assert reports_dir.exists()
    
    # Check for report files (there should be at least one)
    report_files = list(reports_dir.glob("nightly_report_*.txt"))
    assert len(report_files) >= 1
    
    # Read the report and verify contents
    report_text = report_files[0].read_text()
    assert "PANOPTES Nightly Observation Report" in report_text
    assert "OBSERVATIONS SUMMARY" in report_text
    assert "SAFETY SUMMARY" in report_text


def test_housekeeping_handles_empty_observations(db, tmp_path):
    """Test housekeeping with no observations."""
    # Create a mock POCS instance with no observations
    pocs = MockPOCS(db=db, config_dir=tmp_path)
    
    # Create mock event data
    event_data = MockEventData(pocs)
    
    # Call housekeeping on_enter
    housekeeping.on_enter(event_data)
    
    # Check that next_state was set
    assert pocs.next_state == "sleeping"
    
    # Check that report was still generated
    reports_dir = tmp_path / "reports"
    assert reports_dir.exists()
    
    report_files = list(reports_dir.glob("nightly_report_*.txt"))
    assert len(report_files) >= 1
    
    # Verify the report mentions no observations
    report_text = report_files[0].read_text()
    assert "No observations were completed" in report_text


def test_housekeeping_handles_errors_gracefully(tmp_path):
    """Test that housekeeping continues even if report generation fails."""
    # Create a mock POCS with invalid db (None)
    pocs = MockPOCS(db=None, config_dir=tmp_path)
    
    # Create mock event data
    event_data = MockEventData(pocs)
    
    # This should not raise an exception
    housekeeping.on_enter(event_data)
    
    # Check that next_state was still set despite error
    assert pocs.next_state == "sleeping"
