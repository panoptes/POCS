import os
import subprocess

from astropy import units as u
from threading import Event
from threading import Timer

from pocs.utils import current_time
from pocs.utils import error
from pocs.utils import images as img_utils
from pocs.utils.images import fits as fits_utils
from pocs.utils.images import cr2 as cr2_utils
from pocs.camera import AbstractGPhotoCamera


class Camera(AbstractGPhotoCamera):

    def __init__(self, *args, **kwargs):
        kwargs['readout_time'] = 6.0
        kwargs['file_extension'] = 'cr2'
        super().__init__(*args, **kwargs)
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
        if _serial_number > '':
            self._serial_number = _serial_number

        # Properties to be set upon init.
        prop2index = {
            '/main/actions/viewfinder': 1,                # Screen off
            '/main/settings/autopoweroff': 0,             # Don't power off
            '/main/settings/reviewtime': 0,               # Screen off after taking pictures
            '/main/settings/capturetarget': 0,            # Capture to RAM, for download
            '/main/imgsettings/imageformat': 9,           # RAW
            '/main/imgsettings/imageformatsd': 9,         # RAW
            '/main/imgsettings/imageformatcf': 9,         # RAW
            '/main/imgsettings/iso': 1,                   # ISO 100
            '/main/capturesettings/focusmode': 0,         # Manual (don't try to focus)
            '/main/capturesettings/continuousaf': 0,      # No auto-focus
            '/main/capturesettings/autoexposuremode': 3,  # 3 - Manual; 4 - Bulb
            '/main/capturesettings/drivemode': 0,         # Single exposure
            '/main/capturesettings/shutterspeed': 0,      # Bulb
        }
        prop2value = {
            '/main/settings/artist': 'Project PANOPTES',
            '/main/settings/ownername': 'Project PANOPTES',
            '/main/settings/copyright': 'Project PANOPTES {}'.format(current_time().datetime.year),
        }

        self.set_properties(prop2index, prop2value)
        self._connected = True

    def take_observation(self, observation, headers=None, filename=None, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls
        `take_exposure`. Also creates a `threading.Event` object and a
        `threading.Timer` object. The timer calls `process_exposure` after the
        set amount of time is expired (`observation.exp_time + self.readout_time`).

        Note:
            If a `filename` is passed in it can either be a full path that includes
            the extension, or the basename of the file, in which case the directory
            path and extension will be added to the `filename` for output

        Args:
            observation (~pocs.scheduler.observation.Observation): Object
                describing the observation
            headers (dict): Header data to be saved along with the file
            filename (str, optional): Filename for saving, defaults to ISOT time stamp
            **kwargs (dict): Optional keyword arguments (`exp_time`)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        camera_event = Event()

        if headers is None:
            headers = {}

        start_time = headers.get('start_time', current_time(flatten=True))

        # Get the filename
        image_dir = "{}/fields/{}/{}/{}/".format(
            self.config['directories']['images'],
            observation.field.field_name,
            self.uid,
            observation.seq_time,
        )

        # Get full file path
        if filename is None:
            file_path = "{}/{}.{}".format(image_dir, start_time, self.file_extension)
        else:
            # Add extension
            if '.' not in filename:
                filename = '{}.{}'.format(filename, self.file_extension)

            # Add directory
            if '/' not in filename:
                filename = '{}/{}'.format(image_dir, filename)

            file_path = filename

        image_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            start_time
        )
        self.logger.debug("image_id: {}".format(image_id))

        sequence_id = '{}_{}_{}'.format(
            self.config['name'],
            self.uid,
            observation.seq_time
        )

        # Camera metadata
        metadata = {
            'camera_name': self.name,
            'camera_uid': self.uid,
            'field_name': observation.field.field_name,
            'file_path': file_path,
            'filter': self.filter_type,
            'image_id': image_id,
            'is_primary': self.is_primary,
            'sequence_id': sequence_id,
            'start_time': start_time,
        }
        metadata.update(headers)

        exp_time = kwargs.get('exp_time', observation.exp_time.value)
        # The exp_time header data is set as part of observation but can
        # be override by passed parameter so update here.
        metadata['exp_time'] = exp_time

        proc = self.take_exposure(seconds=exp_time, filename=file_path)

        # Add most recent exposure to list
        if self.is_primary:
            observation.exposure_list[image_id] = file_path.replace('.cr2', '.fits')

        # Process the image after a set amount of time
        wait_time = exp_time + self.readout_time
        t = Timer(wait_time, self.process_exposure, (metadata, camera_event, proc))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """Take an exposure for given number of seconds and saves to provided filename

        Note:
            See `scripts/take_pic.sh`

            Tested With:
                * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
        """
        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug(
            'Taking {} second exposure on {}: {}'.format(
                seconds, self.name, filename))

        if isinstance(seconds, u.Quantity):
            seconds = seconds.value

        script_path = '{}/scripts/take_pic.sh'.format(os.getenv('POCS'))

        run_cmd = [script_path, self.port, str(seconds), filename]

        # Take Picture
        try:
            proc = subprocess.Popen(run_cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
        except error.InvalidCommand as e:
            self.logger.warning(e)
        except subprocess.TimeoutExpired:
            self.logger.debug("Still waiting for camera")
            proc.kill()
            outs, errs = proc.communicate(timeout=10)
            if errs is not None:
                self.logger.warning(errs)
        else:
            return proc

    def process_exposure(self, info, signal_event, exposure_process=None):
        """Processes the exposure

        Converts the CR2 to a FITS file. If the camera is a primary camera, extract the
        jpeg image and save metadata to mongo `current` collection. Saves metadata
        to mongo `observations` collection for all images

        Args:
            info (dict): Header metadata saved for the image
            signal_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
        """
        if exposure_process:
            exposure_process.wait()

        image_id = info['image_id']
        seq_id = info['sequence_id']
        file_path = info['file_path']
        self.logger.debug("Processing {}".format(image_id))

        try:
            self.logger.debug("Extracting pretty image")
            img_utils.make_pretty_image(file_path, title=image_id, primary=info['is_primary'])
        except Exception as e:
            self.logger.warning('Problem with extracting pretty image: {}'.format(e))

        self.logger.debug("Converting CR2 -> FITS: {}".format(file_path))
        fits_path = cr2_utils.cr2_to_fits(file_path, headers=info, remove_cr2=True)

        # Replace the path name with the FITS file
        info['file_path'] = fits_path

        if info['is_primary']:
            self.logger.debug("Adding current observation to db: {}".format(image_id))
            self.db.insert_current('observations', info, include_collection=False)
        else:
            self.logger.debug('Compressing {}'.format(file_path))
            fits_utils.fpack(fits_path)

        self.logger.debug("Adding image metadata to db: {}".format(image_id))
        self.db.insert('observations', {
            'data': info,
            'date': current_time(datetime=True),
            'sequence_id': seq_id,
        })

        # Mark the event as done
        signal_event.set()
