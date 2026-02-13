"""Tests for nightly report generation."""
import pytest
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

from panoptes.pocs.utils.report import NightlyReport
from panoptes.pocs.scheduler.observation.base import Observation
from panoptes.pocs.scheduler.field import Field
from panoptes.utils.database import PanDB


@pytest.fixture
def db():
    """Create a test database instance."""
    return PanDB(db_type="memory", db_name="test_report")


@pytest.fixture
def report_generator(db):
    """Create a NightlyReport instance with the test database."""
    return NightlyReport(db=db)


@pytest.fixture
def sample_observations():
    """Create sample observations for testing."""
    observed_list = OrderedDict()
    
    # Create a simple field and observation
    field1 = Field(name="Test Field 1", position="20h00m00s +30d00m00s")
    obs1 = Observation(field=field1, exptime=120, min_nexp=10)
    obs1.seq_time = "2026-02-13T01:00:00"
    
    field2 = Field(name="Test Field 2", position="22h00m00s +40d00m00s")
    obs2 = Observation(field=field2, exptime=120, min_nexp=20)
    obs2.seq_time = "2026-02-13T02:30:00"
    
    observed_list[obs1.seq_time] = obs1
    observed_list[obs2.seq_time] = obs2
    
    return observed_list


def test_report_generator_creation(report_generator):
    """Test that NightlyReport can be created."""
    assert report_generator is not None
    assert report_generator.db is not None


def test_generate_report_empty(report_generator, tmp_path):
    """Test report generation with no observations."""
    output_path = tmp_path / "test_report.txt"
    
    report_text = report_generator.generate_report(
        observed_list={},
        output_path=output_path
    )
    
    assert "PANOPTES Nightly Observation Report" in report_text
    assert "No observations were completed" in report_text
    assert output_path.exists()
    assert output_path.read_text() == report_text


def test_generate_report_with_observations(report_generator, sample_observations, tmp_path):
    """Test report generation with observations."""
    output_path = tmp_path / "test_report.txt"
    
    report_text = report_generator.generate_report(
        observed_list=sample_observations,
        output_path=output_path
    )
    
    assert "PANOPTES Nightly Observation Report" in report_text
    # Field names have spaces removed, so "Test Field 1" becomes "TestField1"
    assert "TestField1" in report_text
    assert "TestField2" in report_text
    assert "Total observation sequences: 2" in report_text
    assert "Unique fields observed: 2" in report_text
    assert output_path.exists()


def test_generate_report_without_file(report_generator, sample_observations):
    """Test report generation without saving to file."""
    report_text = report_generator.generate_report(
        observed_list=sample_observations
    )
    
    assert "PANOPTES Nightly Observation Report" in report_text
    # Field names have spaces removed
    assert "TestField1" in report_text


def test_summarize_observations_empty(report_generator):
    """Test observation summary with no observations."""
    summary = report_generator._summarize_observations({})
    
    summary_text = "\n".join(summary)
    assert "OBSERVATIONS SUMMARY" in summary_text
    assert "No observations were completed" in summary_text


def test_summarize_observations_with_data(report_generator, sample_observations):
    """Test observation summary with observation data."""
    summary = report_generator._summarize_observations(sample_observations)
    
    summary_text = "\n".join(summary)
    assert "OBSERVATIONS SUMMARY" in summary_text
    # Field names have spaces removed
    assert "TestField1" in summary_text
    assert "TestField2" in summary_text
    assert "2 sequence(s)" in summary_text or "1 sequence(s)" in summary_text


def test_summarize_safety_no_data(report_generator):
    """Test safety summary with no safety data in database."""
    summary = report_generator._summarize_safety_checks()
    
    summary_text = "\n".join(summary)
    assert "SAFETY SUMMARY" in summary_text
    assert "No safety data available" in summary_text


def test_summarize_safety_all_safe(report_generator, db):
    """Test safety summary with all checks passing."""
    # Insert safe conditions into database
    safety_data = {
        "ac_power": True,
        "is_dark": True,
        "good_weather": True,
        "free_space_root": True,
        "free_space_images": True
    }
    db.insert_current("safety", safety_data)
    
    summary = report_generator._summarize_safety_checks()
    
    summary_text = "\n".join(summary)
    assert "SAFETY SUMMARY" in summary_text
    assert "All safety checks passed" in summary_text
    assert "✓ PASS" in summary_text


def test_summarize_safety_with_failures(report_generator, db):
    """Test safety summary with failing checks."""
    # Insert unsafe conditions into database
    safety_data = {
        "ac_power": True,
        "is_dark": False,
        "good_weather": False,
        "free_space_root": True,
        "free_space_images": True
    }
    db.insert_current("safety", safety_data)
    
    summary = report_generator._summarize_safety_checks()
    
    summary_text = "\n".join(summary)
    assert "SAFETY SUMMARY" in summary_text
    assert "WARNING: Some safety checks failed" in summary_text
    assert "✗ FAIL" in summary_text
    assert "Unsafe weather conditions" in summary_text
    assert "Not dark enough" in summary_text


def test_report_date_format(report_generator):
    """Test that report includes proper date formatting."""
    report_text = report_generator.generate_report(observed_list={})
    
    # Should have a date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in report_text


def test_multiple_observations_same_field(report_generator):
    """Test handling of multiple observations of the same field."""
    observed_list = OrderedDict()
    
    field = Field(name="Repeated Field", position="20h00m00s +30d00m00s")
    
    for i in range(3):
        obs = Observation(field=field, exptime=120, min_nexp=10)
        seq_time = f"2026-02-13T0{i}:00:00"
        obs.seq_time = seq_time
        observed_list[seq_time] = obs
    
    summary = report_generator._summarize_observations(observed_list)
    summary_text = "\n".join(summary)
    
    # Field name has spaces removed: "Repeated Field" becomes "RepeatedField"
    assert "RepeatedField: 3 sequence(s)" in summary_text
    assert "Total observation sequences: 3" in summary_text
    assert "Unique fields observed: 1" in summary_text
