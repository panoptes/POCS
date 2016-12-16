from threading import Thread, Event

from astropy import units as u
from astropy.io import fits

from ..utils import error
from .camera import AbstractCamera
from .sbigudrv import SBIGDriver, INVALID_HANDLE_VALUE
from ..utils import current_time


class Camera(AbstractCamera):

    # Class variable to store reference to the one and only one instance of SBIGDriver
    _SBIGDriver = None

    def __new__(cls, *args, **kwargs):
        if Camera._SBIGDriver is None:
            # Creating a camera but there's no SBIGDriver instance yet. Create one.
            Camera._SBIGDriver = SBIGDriver(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self,
                 name='SBIG Camera',
                 set_point=None,
                 *args, **kwargs):
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)
        self.logger.debug("Connecting SBIG camera")
        self.connect(set_point)
        self.logger.debug("{} connected".format(self.name))

# Properties

    @property
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
        return self._serial_number

    @property
    def CCD_temp(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDTemperature * u.Celsius

    @property
    def CCD_set_point(self):
        return self._SBIGDriver.query_temp_status(self._handle).ccdSetpoint * u.Celsius

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        self._SBIGDriver.set_temp_regulation(self._handle, set_point)

    @property
    def CCD_cooling_enabled(self):
        return bool(self._SBIGDriver.query_temp_status(self._handle).coolingEnabled)

    @property
    def CCD_cooling_power(self):
        return self._SBIGDriver.query_temp_status(self._handle).imagingCCDPower

# Methods

    def __str__(self):
        # uid and port are both aliases for serial number so shouldn't include both
        return "{}({})".format(self.name, self.uid)

    def connect(self, set_point=None):
        """
        Connect to SBIG camera.

        Gets a 'handle', serial number and specs/capabilities from the driver

        Args:
            set_point (u.Celsius, optional): CCD cooling set point. If not given cooling will be disabled.
        """
        self.logger.debug('Connecting to camera {}'.format(self.uid))

        # Claim handle from the SBIGDriver, store camera info.
        self._handle, self._info = self._SBIGDriver.assign_handle(serial=self.port)

        if self._handle == INVALID_HANDLE_VALUE:
            self.logger.warning('Could not connect to {}!'.format(self.name))
            self._connected = False
            return

        self._connected = True
        self._serial_number = self._info['serial_number']

        if self._info['colour']:
            if self._info['Truesense']:
                self.filter_type = 'CRGB'
            else:
                self.filter_type = 'RGGB'
        else:
            self.filter_type = 'M'

        # Set cooling (if set_point=None this will turn off cooling)
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        self._SBIGDriver.set_temp_regulation(self._handle, set_point)

    def take_observation(self, observation, headers, **kwargs):
        """Take an observation

        Gathers various header information, sets the file path, and calls `take_exposure`. Also creates a
        `threading.Event` object and a `threading.Timer` object. The timer calls `process_exposure` after the
        set amount of time is expired (`observation.exp_time + self.readout_time`).

        Args:
            observation (~pocs.scheduler.observation.Observation): Object describing the observation
            headers (dict): Header data to be saved along with the file
            **kwargs (dict): Optional keyword arguments (`exp_time`, dark)

        Returns:
            threading.Event: An event to be set when the image is done processing
        """
        # To be used for marking when exposure is complete (see `process_exposure`)
        camera_event = Event()

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
        exp_time = kwargs.get('exp_time', observation.exp_time)

        exposure_event = self.take_exposure(seconds=exp_time, filename=file_path)

        # Process the exposure once readout is complete
        t = Thread(wait_time, self.process_exposure, (metadata, camera_event, exposure_event))
        t.name = '{}Thread'.format(self.name)
        t.start()

        return camera_event

    def take_exposure(self, seconds=1.0 * u.second, filename=None, dark=False, blocking=False):
        """
        Take an exposure for given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        self.logger.debug('Taking {} second exposure on {}: {}'.format(seconds, self.name, filename))
        exposure_event = Event()
        self._SBIGDriver.take_exposure(self._handle, seconds, filename, exposure_event, dark)

        if blocking:
            exposure_event.wait()

        return exposure_event

    def process_exposure(self, info, signal_event, exposure_event=None):
        """
        Processes the exposure

        Args:
            info (dict): Header metadata saved for the image
            signal_event (threading.Event): An event that is set signifying that the
                camera is done with this exposure
            exposure_event (threading.Event, optional): An event that should be set
                when the exposure is complete, triggering the processing.
        """
        # If passed an Event that signals the end of the exposure wait for it to be set
        if exposure_event:
            exposure_event.wait()

        image_id = info['image_id']
        file_path = info['file_path']
        self.logger.debug("Processing {}".format(image_id))

        # Add FITS headers from info the same as images.cr2_to_fits()
        self.logger.debug("Updating FITS headers: {}".format(file_path))
        with fits.open(file_path, 'update') as f:
            hdu = f[0]
            hdu.header.set('IMAGEID', info.get('image_id', ''))
            hdu.header.set('SEQID', info.get('sequence_id', ''))
            hdu.header.set('FIELD', info.get('field_name', ''))
            hdu.header.set('RA-MNT', info.get('ra_mnt', ''), 'Degrees')
            hdu.header.set('HA-MNT', info.get('ha_mnt', ''), 'Degrees')
            hdu.header.set('DEC-MNT', info.get('dec_mnt', ''), 'Degrees')
            hdu.header.set('EQUINOX', info.get('equinox', ''))
            hdu.header.set('AIRMASS', info.get('airmass', ''), 'Sec(z)')
            hdu.header.set('FILTER', info.get('filter', ''))
            hdu.header.set('LAT-OBS', info.get('latitude', ''), 'Degrees')
            hdu.header.set('LONG-OBS', info.get('longitude', ''), 'Degrees')
            hdu.header.set('ELEV-OBS', info.get('elevation', ''), 'Meters')
            hdu.header.set('MOONSEP', info.get('moon_separation', ''), 'Degrees')
            hdu.header.set('MOONFRAC', info.get('moon_fraction', ''))
            hdu.header.set('CREATOR', info.get('creator', ''), 'POCS Software version')
            hdu.header.set('INSTRUME', info.get('camera_uid', ''), 'Camera ID')
            hdu.header.set('OBSERVER', info.get('observer', ''), 'PANOPTES Unit ID')
            hdu.header.set('ORIGIN', info.get('origin', ''))
            hdu.header.set('RA-RATE', headers.get('tracking_rate_ra', ''), 'RA Tracking Rate')

        if info['is_primary']:
            self.logger.debug("Extracting pretty image")
            images.make_pretty_image(file_path, title=info['field_name'], primary=True)

            self.logger.debug("Adding current observation to db: {}".format(image_id))
            self.db.insert_current('observations', info, include_collection=False)
        else:
            self.logger.debug('Compressing {}'.format(file_path))
            images.fpack(file_path)

        self.logger.debug("Adding image metadata to db: {}".format(image_id))
        self.db.observations.insert_one({
            'data': info,
            'date': current_time(datetime=True),
            'type': 'observations',
            'image_id': image_id,
        })

        # Mark the event as done
        signal_event.set()
