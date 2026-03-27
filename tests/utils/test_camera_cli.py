import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from astropy.io import fits
from typer.testing import CliRunner

from panoptes.pocs.utils.cli.main import app


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_take_bias_isolates_runs(cli_runner, tmp_path):
    """Test that take-bias only processes files from the current run."""
    # Create a base bias directory
    bias_dir = tmp_path / "bias"
    bias_dir.mkdir()

    # Create an "old" run directory with a file that should be ignored
    old_run_dir = bias_dir / "20240101T000000"
    old_run_dir.mkdir()
    old_file = old_run_dir / "cam00-0000-20240101T000000.fits"

    # Create a dummy FITS file for the old run
    hdu = fits.PrimaryHDU(data=np.zeros((10, 10)))
    hdu.writeto(old_file)

    # Mock cameras
    mock_cam = MagicMock()
    mock_cam.name = "cam00"
    mock_cam.uid = "cam00"
    mock_cam.file_extension = "fits"

    # We need to mock current_time to return a predictable timestamp for the "new" run
    # or just let it do its thing.

    with (
        patch("panoptes.pocs.utils.cli.camera.create_cameras_from_config") as mock_create,
        patch("panoptes.pocs.utils.cli.camera.getdata") as mock_getdata,
        patch("panoptes.pocs.utils.cli.camera.sigma_clipped_stats") as mock_stats,
    ):
        mock_create.return_value = {"cam00": mock_cam}
        mock_getdata.return_value = np.ones((10, 10))
        mock_stats.return_value = (1.0, 1.0, 0.0)  # mean, median, std

        # We need to make sure the "new" file actually exists so getdata doesn't fail
        # take_pictures calls _take_pics which calls take_exposure.
        # We'll mock take_exposure to actually create the file.
        def side_effect(seconds, filename, **kwargs):
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            hdu = fits.PrimaryHDU(data=np.ones((10, 10)))
            hdu.writeto(filename)

        mock_cam.take_exposure.side_effect = side_effect

        # Run the command with num-images=1
        cmd = [
            "camera",
            "take-bias",
            "--num-images",
            "1",
            "--output-dir",
            str(bias_dir),
        ]
        result = cli_runner.invoke(app, cmd)

        assert result.exit_code == 0

        # Verify that only 1 bias frame was processed for cam00
        # If the bug was present, it would find both the old and new files and say "Processing 2 bias frames"
        assert "Processing 1 bias frames for cam00" in result.output
        assert "Processing 2 bias frames for cam00" not in result.output

        # Verify the master bias was saved in the timestamped subfolder
        # We can find the subfolder by looking at the output, accounting for potential newlines
        # Match "Master bias saved to:" followed by any characters including newlines until ".fits"
        match = re.search(r"Master bias saved to:\s+(.*\.fits)", result.output, re.DOTALL)
        assert match is not None

        # Clean up the path (remove newlines and extra spaces)
        path_str = match.group(1).replace("\n", "").strip()
        master_bias_path = Path(path_str)

        assert master_bias_path.exists()
        assert master_bias_path.parent != bias_dir  # It should be in a subfolder
        assert master_bias_path.parent.parent == bias_dir
