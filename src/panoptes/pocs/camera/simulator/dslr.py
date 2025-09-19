"""DSLR-style simulated camera driver.

Provides a lightweight Camera implementation that mimics a DSLR controlled via
simple timers and sample FITS data, suitable for tests and demos.
"""
import os
import random
from threading import Timer

import numpy as np
from astropy import units as u
from astropy.io import fits
from panoptes.utils.images import fits as fits_utils
from panoptes.utils.time import CountdownTimer
from panoptes.utils.utils import get_quantity_value

from panoptes.pocs.camera import AbstractCamera


class Camera(AbstractCamera):
    """Simulated DSLR-like camera using timers and canned FITS data."""

    @property
    def egain(self):
        """Estimated sensor gain (e-/ADU) used for testing.

        Returns:
            int | float: Constant gain value for the simulator (unitless).
        """
        return 1

    @property
    def bit_depth(self):
        """ADC bit depth for the simulated sensor.

        Returns:
            astropy.units.Quantity: Bit depth in bits.
        """
        return 12 * u.bit

    def __init__(self, name="Simulated Camera", *args, **kwargs):
        """Create the simulated camera and connect immediately.

        Args:
            name (str): Friendly name for the simulated camera.
            *args: Forwarded to AbstractCamera.
            **kwargs: Forwarded to AbstractCamera; supports timeout and readout_time.
        """
        kwargs["timeout"] = kwargs.get("timeout", 1.5 * u.second)
        kwargs["readout_time"] = kwargs.get("readout_time", 1.0 * u.second)
        super().__init__(name=name, *args, **kwargs)
        # Create a random serial number if one hasn't been specified
        if self._serial_number == "XXXXXX":
            self._serial_number = "SC{:04d}".format(random.randint(0, 9999))

        self.connect()
        self.logger.debug(f"{self.name} connected")
        self.setup_camera()
        self.logger.info(f"{self} initialised")

    def connect(self):
        """Connect to the camera simulator.

        This is a no-op for the simulator.
        """
        self.logger.debug(f"Connecting to camera simulator {self.name}")
        self._connected = True

    def setup_camera(self):
        """Set up the camera simulator.

        This is a no-op for the simulator.
        """
        self.logger.debug(f"Setting up camera simulator {self.name}")
        pass

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):
        """Start a simulated observation, trimming long exposures.

        For the simulator, any requested exposure longer than 1 second is
        reduced to 1 second to keep tests fast.

        Args:
            observation: The Observation describing the target/sequence.
            headers: Optional FITS header metadata to include.
            filename: Optional filename stem to use for the output.
            *args: Forwarded to AbstractCamera.take_observation.
            **kwargs: May include 'exptime' to set the exposure duration.

        Returns:
            dict: The metadata returned by AbstractCamera.take_observation.
        """
        exptime = kwargs.get("exptime", observation.exptime.value)
        if exptime > 1:
            kwargs["exptime"] = 1
            self.logger.debug("Trimming camera simulator exposure to 1 s")

        return super().take_observation(observation, headers, filename, **kwargs)

    def _end_exposure(self):
        self._is_exposing_event.clear()

    def _start_exposure(
        self, seconds=None, filename=None, dark=False, header=None, *args, **kwargs
    ):
        self._is_exposing_event.set()
        seconds = kwargs.get("simulator_exptime", seconds)
        exposure_thread = Timer(
            interval=get_quantity_value(seconds, unit=u.second), function=self._end_exposure
        )
        exposure_thread.start()
        readout_args = (filename, header)
        return readout_args

    def _readout(self, filename=None, header=None):
        self.logger.debug(f"Calling _readout for {self}")
        timer = CountdownTimer(duration=self.readout_time, name="ReadoutDSLR")
        # Get example FITS file from test data directory
        file_path = os.path.join(".", "tests", "data", "unsolved.fits")
        fake_data = fits.getdata(file_path)

        if header.get("IMAGETYP") == "Dark Frame":
            # Replace example data with a bunch of random numbers
            fake_data = np.random.randint(
                low=975, high=1026, size=fake_data.shape, dtype=fake_data.dtype
            )
        self.logger.debug(f"Writing filename={filename!r} for {self}")
        self.write_fits(fake_data, header, filename)
        self.logger.debug(f"Finished writing {filename=}")

        # Sleep for the remainder of the readout time.
        timer.sleep()

    def _do_process_exposure(self, file_path, metadata):
        file_path = super()._do_process_exposure(file_path, metadata)
        self.logger.debug("Overriding mount coordinates for camera simulator")
        # TODO get the path as package data or something better.
        solved_path = os.path.join(".", "tests", "data", "solved.fits.fz")
        solved_header = fits_utils.getheader(solved_path)
        with fits.open(file_path, "update") as f:
            hdu = f[0]
            hdu.header.set("RA-MNT", solved_header["RA-MNT"], "Degrees")
            hdu.header.set("HA-MNT", solved_header["HA-MNT"], "Degrees")
            hdu.header.set("DEC-MNT", solved_header["DEC-MNT"], "Degrees")

        self.logger.debug("Headers updated for simulated image.")
        return file_path

    def _set_target_temperature(self, target):
        raise False

    def _set_cooling_enabled(self, enable):
        raise False
