import os
import subprocess

from astropy import units as u
from threading import Event, Timer

from ..utils import error
from .camera import AbstractGPhotoCamera
from .utils import current_time
from .utils import images


class Camera(AbstractGPhotoCamera):

    def __init__(self, *args, **kwargs):
        kwargs['readout_time'] = 6.0
        kwargs['file_extension'] = 'cr2'
        super().__init__(*args, **kwargs)
        self.logger.debug("Connecting GPhoto2 camera")
        self.connect()
        self.logger.debug("{} connected".format(self.name))

    def connect(self):
        """
        For Canon DSLRs using gphoto2, this just means confirming that there is
        a camera on that port and that we can communicate with it.
        """
        self.logger.debug('Connecting to camera')

        # Get serial number
        _serial_number = self.get_property('serialnumber')
        if _serial_number > '':
            self._serial_number = _serial_number

        self.set_property('/main/actions/viewfinder', 1)       # Screen off
        self.set_property('/main/settings/autopoweroff', 0)     # Don't power off
        self.set_property('/main/settings/reviewtime', 0)       # Screen off
        self.set_property('/main/settings/capturetarget', 0)    # Internal RAM (for download)
        self.set_property('/main/settings/artist', 'Project PANOPTES')
        self.set_property('/main/settings/ownername', 'Project PANOPTES')
        self.set_property('/main/settings/copyright', 'Project PANOPTES 2016')
        self.set_property('/main/imgsettings/imageformat', 9)       # RAW
        self.set_property('/main/imgsettings/imageformatsd', 9)     # RAW
        self.set_property('/main/imgsettings/imageformatcf', 9)     # RAW
        self.set_property('/main/imgsettings/iso', 1)               # ISO 100
        self.set_property('/main/capturesettings/focusmode', 0)         # Manual
        self.set_property('/main/capturesettings/continuousaf', 0)         # No AF
        self.set_property('/main/capturesettings/autoexposuremode', 3)  # 3 - Manual; 4 - Bulb
        self.set_property('/main/capturesettings/drivemode', 0)         # Single exposure
        self.set_property('/main/capturesettings/shutterspeed', 0)      # Bulb
        # self.set_property('/main/actions/syncdatetime', 1)  # Sync date and time to computer
        # self.set_property('/main/actions/uilock', 1)        # Don't let the UI change

        self._connected = True

    def take_observation(self, observation, headers):
        image_dir = self.config['directories']['images']
        start_time = headers.get('start_time', current_time(flatten=True))

        filename = "{}/{}/{}/{}.{}".format(
            observation.field.field_name,
            self.uid,
            observation.seq_time,
            start_time,
            self.file_extension)

        file_path = "{}/fields/{}".format(image_dir, filename)

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

        camera_event = Event()
        # Take the exposure and get an Event back to mark when done
        self.take_exposure(seconds=observation.exp_time, filename=file_path)

        # Process the image after a set amount of time
        wait_time = observation.exp_time.value + self.readout_time
        Timer(wait_time, self.process_exposure, (metadata, camera_event,)).start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None):
        """Take an exposure for given number of seconds

        Note:
            See `scripts/take_pic.sh`

            Tested With:
                * Canon EOS 100D

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
        """
        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug('Taking {} second exposure on {}: {}'.format(seconds, self.name, filename))

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        script_path = '{}/scripts/take_pic.sh'.format(os.getenv('POCS'))

        run_cmd = [script_path, self.port, str(seconds.value), filename]

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

    def process_exposure(self, info, signal_event):
        image_id = info['image_id']
        file_path = info['file_path']
        self.logger.debug("Processing {}".format(image_id))

        self.logger.debug("Converting CR2 -> FITS: {}".format(file_path))
        fits_path = images.cr2_to_fits(file_path, headers=info, remove_cr2=True)

        # Replace the path name with the FITS file
        info['file_path'] = fits_path

        if info['is_primary']:
            self.logger.debug("Extracting pretty image")
            images.make_pretty_image(file_path, title=info['field_name'], primary=True)

            self.logger.debug("Adding current observation to db: {}".format(image_id))
            self.db.insert_current('observations', info, include_collection=False)
        else:
            self.logger.debug('Compressing {}'.format(file_path))
            images.fpack(fits_path)

        self.logger.debug("Adding image metadata to db: {}".format(image_id))
        self.db.observations.insert_one({
            'data': info,
            'date': current_time(datetime=True),
            'type': 'observations',
            'image_id': image_id,
        })

        # Mark the event as done
        signal_event.set()
