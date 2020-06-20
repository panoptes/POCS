import os
import subprocess
from abc import ABC

from threading import Event
from threading import Timer

from panoptes.utils import current_time
from panoptes.utils import CountdownTimer
from panoptes.utils import error
from panoptes.utils import get_quantity_value
from panoptes.utils.images import cr2 as cr2_utils
from panoptes.pocs.camera import AbstractGPhotoCamera


class Camera(AbstractGPhotoCamera, ABC):

    def __init__(self, *args, **kwargs):
        kwargs['readout_time'] = 6.0
        kwargs['file_extension'] = 'cr2'
        super().__init__(*args, **kwargs)

        # Hold on to the exposure process for polling.
        self._exposure_proc = None

        self.logger.debug("Connecting GPhoto2 camera")
        self.connect()
        self.logger.debug("{} connected".format(self.name))

    def connect(self):
        """Connect to Canon DSLR

        Gets the serial number from the camera and sets various settings
        """
        self.logger.debug('Connecting to camera')

        # Get serial number
        _serial_number = self.get_property('serialnumber')
        if not _serial_number:
            raise error.CameraNotFound(f"Camera not responding: {self}")

        self._serial_number = _serial_number

        # Properties to be set upon init.
        prop2index = {
            '/main/actions/viewfinder': 1,  # Screen off
            '/main/capturesettings/autoexposuremode': 3,  # 3 - Manual; 4 - Bulb
            '/main/capturesettings/continuousaf': 0,  # No auto-focus
            '/main/capturesettings/drivemode': 0,  # Single exposure
            '/main/capturesettings/focusmode': 0,  # Manual (don't try to focus)
            '/main/capturesettings/shutterspeed': 0,  # Bulb
            '/main/imgsettings/imageformat': 9,  # RAW
            '/main/imgsettings/imageformatcf': 9,  # RAW
            '/main/imgsettings/imageformatsd': 9,  # RAW
            '/main/imgsettings/iso': 1,  # ISO 100
            '/main/settings/autopoweroff': 0,  # Don't power off
            '/main/settings/capturetarget': 0,  # Capture to RAM, for download
            '/main/settings/datetime': 'now',  # Current datetime
            '/main/settings/datetimeutc': 'now',  # Current datetime
            '/main/settings/reviewtime': 0,  # Screen off after taking pictures
        }

        owner_name = 'Project PANOPTES'
        artist_name = self.get_config('pan_id', default=owner_name)
        copyright = f'{owner_name} {current_time().datetime:%Y}'

        prop2value = {
            '/main/settings/artist': artist_name,
            '/main/settings/copyright': copyright,
            '/main/settings/ownername': owner_name,
        }

        self.set_properties(prop2index, prop2value)
        self._connected = True

    def take_observation(self, observation, headers=None, filename=None, *args, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls
        `take_exposure`. Also creates a `threading.Event` object and a
        `threading.Timer` object. The timer calls `process_exposure` after the
        set amount of time is expired (`observation.exptime + self.readout_time`).

        Note:
            If a `filename` is passed in it can either be a full path that includes
            the extension, or the basename of the file, in which case the directory
            path and extension will be added to the `filename` for output

        Args:
            observation (~pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict): Header data to be saved along with the file
            filename (str, optional): Filename for saving, defaults to ISOT time stamp
            **kwargs (dict): Optional keyword arguments (`exptime`)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        observation_event = Event()

        exptime, file_path, image_id, metadata = self._setup_observation(observation,
                                                                         headers,
                                                                         filename,
                                                                         **kwargs)

        exposure_event = self.take_exposure(seconds=exptime, filename=file_path)

        # Add most recent exposure to list
        if self.is_primary:
            if 'POINTING' in headers:
                observation.pointing_images[image_id] = file_path.replace('.cr2', '.fits')
            else:
                observation.exposure_list[image_id] = file_path.replace('.cr2', '.fits')

        # Process the image after a set amount of time
        wait_time = exptime + self.readout_time

        t = Timer(wait_time, self.process_exposure, (metadata, observation_event, exposure_event))
        t.name = f'{self.name}Thread'
        t.start()

        return observation_event

    def _start_exposure(self, seconds=None, filename=None, dark=None, header=None, *args, **kwargs):
        """Take an exposure for given number of seconds and saves to provided filename

        Note:
            See `scripts/take-pic.sh`

            Tested With:
                * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
        """
        script_path = os.path.expandvars('$POCS/scripts/take-pic.sh')

        # Make sure we have just the value, no units
        seconds = get_quantity_value(seconds)

        run_cmd = [script_path, self.port, str(seconds), filename]

        # Take Picture
        try:
            self._is_exposing = True
            self._exposure_proc = subprocess.Popen(run_cmd,
                                                   stdout=subprocess.PIPE,
                                                   stderr=subprocess.PIPE,
                                                   universal_newlines=True)
        except error.InvalidCommand as e:
            self.logger.warning(e)
        finally:
            readout_args = (filename, header)
            return readout_args

    def _readout(self, cr2_path=None, info=None):
        """Reads out the image as a CR2 and converts to FITS"""
        self.logger.debug(f"Converting CR2 -> FITS: {cr2_path}")
        fits_path = cr2_utils.cr2_to_fits(cr2_path, headers=info, remove_cr2=False)
        return fits_path

    def _process_fits(self, file_path, info):
        """
        Add FITS headers from info the same as images.cr2_to_fits()
        """
        file_path = file_path.replace('.cr2', '.fits')
        return super()._process_fits(file_path, info)

    def _poll_exposure(self, readout_args):
        timer = CountdownTimer(duration=self._timeout)
        try:
            try:
                # See if the command has finished.
                while self._exposure_proc.poll() is None:
                    # Sleep if not done yet.
                    timer.sleep()
            except subprocess.TimeoutExpired:
                self.logger.warning(f'Timeout on exposure process for {self.name}')
                self._exposure_proc.kill()
                outs, errs = self._exposure_proc.communicate(timeout=10)
                if errs is not None and errs > '':
                    self.logger.error(f'Camera exposure errors: {errs}')
        except (RuntimeError, error.PanError) as err:
            # Error returned by driver at some point while polling
            self.logger.error('Error while waiting for exposure on {}: {}'.format(self, err))
            raise err
        else:
            # Camera type specific readout function
            self._readout(*readout_args)
        finally:
            self.logger.debug(f'Setting exposure event for {self.name}')
            self._is_exposing = False
            self._exposure_proc = None
            self._exposure_event.set()  # Make sure this gets set regardless of readout errors
