"""Canon DSLR camera driver using gphoto2.

Provides a concrete Camera subclass for Canon EOS models controlled via gphoto2.
Implements exposure sequencing, property setup, and a shutterspeed index helper
compatible with the CLI-driven gphoto2 interface.
"""

from functools import lru_cache

from astropy import units as u
from panoptes.utils import error
from panoptes.utils.error import PanError
from panoptes.utils.time import current_time
from panoptes.utils.utils import get_quantity_value

from panoptes.pocs.camera.gphoto.base import AbstractGPhotoCamera


class Camera(AbstractGPhotoCamera):
    """Canon EOS DSLR implementation using gphoto2.

    Provides Canon-specific property defaults and exposure sequencing on top of
    AbstractGPhotoCamera.
    """

    def __init__(
        self,
        readout_time: float = 1.0,
        file_extension: str = "cr2",
        setup_properties: bool = False,
        *args,
        **kwargs,
    ):
        """Create a camera object for a Canon EOS DSLR.

        Args:
            readout (float): The time it takes to read out the file from the
                camera, default 1.0 second.
            file_extension (str): The file extension to use, default `cr2`.
            setup_properties (bool): If True, will call `setup_camera()` to set
                properties on the camera.
        """
        kwargs["readout_time"] = readout_time
        kwargs["file_extension"] = file_extension
        super().__init__(*args, **kwargs)
        self.logger.debug("Creating Canon DSLR GPhoto2 camera")

        self.connect()

        if setup_properties:
            self.setup_camera()

    @property
    def bit_depth(self):
        """ADC bit depth reported by the camera.

        Returns:
            astropy.units.Quantity: The analog-to-digital converter resolution in bits.
        """
        return 12 * u.bit

    @property
    def egain(self):
        """Estimated sensor gain (e-/ADU).

        Returns:
            astropy.units.Quantity: Electrons per ADU, used for photometric calibration.
        """
        return 1.5 * (u.electron / u.adu)

    def connect(self):
        """Connect to the camera.

        This will attempt to connect to the camera using gphoto2.
        """
        # Get serial number
        _serial_number = self.get_property("serialnumber")
        if not _serial_number:
            raise error.CameraNotFound(f"Camera not responding: {self}")

        self._serial_number = _serial_number
        self._connected = True

    def setup_camera(self):
        """Set up the camera.

        Usually called as part of an initial setup, this will set properties
        on the canon cameras that should persist across power cycles.
        """
        # Properties to be set upon init.
        owner_name = "PANOPTES"
        artist_name = self.get_config("pan_id", default=owner_name)
        copy_right = f"{owner_name}_{current_time().datetime:%Y}"

        prop2value = {
            "drivemode": "Single",
            "focusmode": "Manual",
            "imageformat": "RAW",
            # 'autoexposuremode': 'Manual',  # Need physical toggle.
            # 'imageformatsd': 'RAW',  # We shouldn't need to set this.
            "capturetarget": "Memory Card",
            "reviewtime": "None",
            "iso": 100,
            "shutterspeed": "bulb",
            "artist": artist_name,
            "copyright": copy_right,
            "ownername": owner_name,
            "datetime": "now",
            "datetimeutc": "now",
        }

        self.set_properties(prop2value=prop2value)

        self.model = self.get_property("model")

    def _start_exposure(
        self, seconds=None, filename=None, dark=False, header=None, iso=100, *args, **kwargs
    ):
        """Start the exposure.

        Tested With:
            * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure.
            filename (str, optional): Image is saved to this filename.
            header (dict or Header, optional): The metadata to be added as FITS headers.
            iso (int, optional): The ISO setting to use for the exposure, default 100.
        """
        # Make sure we have just the value, no units
        seconds = get_quantity_value(seconds)

        shutterspeed_idx = self.get_shutterspeed_index(seconds=seconds, return_minimum=True)

        cmd_args = [
            "--set-config",
            f"iso={iso}",
            "--filename",
            f"{filename}",
            "--set-config-index",
            f"shutterspeed={shutterspeed_idx}",
            "--wait-event=1s",
        ]

        if shutterspeed_idx == 0:
            # Bulb setting.
            cmd_args.extend(
                [
                    "--set-config-index",
                    "eosremoterelease=2",
                    f"--wait-event={int(seconds):d}s",
                    "--set-config-index",
                    "eosremoterelease=4",
                    "--wait-event-and-download=CAPTURECOMPLETE",
                ]
            )
        else:
            # Known shutterspeed value.
            cmd_args.extend(
                [
                    "--capture-image-and-download",
                ]
            )

        try:
            self.command(cmd_args, check_exposing=False)
        except error.InvalidCommand as e:
            self.logger.warning(e)
            raise PanError(f"Problem taking picture with {self.name}: {e}")
        else:
            readout_args = (filename, header)
            return readout_args

    @classmethod
    @lru_cache(maxsize=52)
    def get_shutterspeed_index(cls, seconds: float, return_minimum: bool = False):
        """Look up the gphoto2 shutterspeed index for a given exposure time.

        Args:
            seconds (float): Desired exposure length in seconds.
            return_minimum (bool): If True and the requested time is shorter than
                the minimum supported shutterspeed, return the index of the
                shortest available speed instead of 0 (bulb). Defaults to False.

        Returns:
            int: The index expected by gphoto2 for the nearest matching shutter
                speed. Returns 0 to indicate 'bulb' when no direct match is found,
                unless return_minimum is True and the time is below the minimum
                discrete setting.
        """
        seconds = get_quantity_value(seconds, unit="second")
        # TODO derive these from `load_properties`.
        # The index corresponds to what gphoto2 expects.
        shutter_speeds = {
            "bulb": "bulb",
            "30": 30,
            "25": 25,
            "20": 20,
            "15": 15,
            "13": 13,
            "10.3": 10.3,
            "8": 8,
            "6.3": 6.3,
            "5": 5,
            "4": 4,
            "3.2": 3.2,
            "2.5": 2.5,
            "2": 2,
            "1.6": 1.6,
            "1.3": 1.3,
            "1": 1,
            "0.8": 0.8,
            "0.6": 0.6,
            "0.5": 0.5,
            "0.4": 0.4,
            "0.3": 0.3,
            "1/4": 1 / 4,
            "1/5": 1 / 5,
            "1/6": 1 / 6,
            "1/8": 1 / 8,
            "1/10": 1 / 10,
            "1/13": 1 / 13,
            "1/15": 1 / 15,
            "1/20": 1 / 20,
            "1/25": 1 / 25,
            "1/30": 1 / 30,
            "1/40": 1 / 40,
            "1/50": 1 / 50,
            "1/60": 1 / 60,
            "1/80": 1 / 80,
            "1/100": 1 / 100,
            "1/125": 1 / 125,
            "1/160": 1 / 160,
            "1/200": 1 / 200,
            "1/250": 1 / 250,
            "1/320": 1 / 320,
            "1/400": 1 / 400,
            "1/500": 1 / 500,
            "1/640": 1 / 640,
            "1/800": 1 / 800,
            "1/1000": 1 / 1000,
            "1/1250": 1 / 1250,
            "1/1600": 1 / 1600,
            "1/2000": 1 / 2000,
            "1/2500": 1 / 2500,
            "1/3200": 1 / 3200,
            "1/4000": 1 / 4000,
        }

        try:
            # First check by key.
            return list(shutter_speeds.keys()).index(seconds)
        except ValueError:
            # Then check by value.
            try:
                # Check minimum of everything after 'bulb'.
                if return_minimum and seconds < min(list(shutter_speeds.values())[1:]):
                    return len(shutter_speeds) - 1
                else:
                    return list(shutter_speeds.values()).index(seconds)
            except ValueError:
                return 0
