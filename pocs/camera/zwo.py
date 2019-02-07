import time
import threading
from warnings import warn
from contextlib import suppress

from astropy import units as u

from pocs.camera.camera import AbstractCamera
from pocs.camera import libasi
from pocs.utils.images import fits as fits_utils
from pocs.utils import error
from pocs.utils import CountdownTimer
from pocs.utils.logger import get_root_logger
from pocs.utils import get_quantity_value


class Camera(AbstractCamera):

    _ASIDriver = None  # Class variable to store the ASI driver interface
    _ids = []  # Cache of camera string IDs
    _assigned_ids = []  # Camera string IDs already in use.

    def __init__(self,
                 name='ZWO ASI Camera',
                 filter_type=None,
                 library_path=None,
                 timeout=1 * u.second,
                 *args, **kwargs):
        # ZWO ASI cameras don't have a 'port', they only have a non-deterministic integer
        # camera_ID and, optionally, an 8 byte ID that can be written to the camera firmware
        # by the user (using ASICap, or pocs.camera.libasi.ASIDriver.set_ID()). We will use
        # the latter as a serial number string.
        kwargs['port'] = None
        kwargs['file_extension'] = 'fits'
        kwargs['readout_time'] = kwargs.get('readout_time', 0.1)

        # Maximum time to wait beyond exposure time for an exposure to complete
        self._timeout = get_quantity_value(timeout, unit=u.second)

        # Create a lock that wil be used to prevent overlapping exposures
        self._exposure_lock = threading.Lock()

        if Camera._ASIDriver is None:
            # Initialise the driver if it hasn't already been done
            Camera._ASIDriver = libasi.ASIDriver(library_path=library_path)

        logger = get_root_logger()
        serial_number = kwargs.get('serial_number')
        if not serial_number:
            msg = "Must specify serial_number (string ID) for ZWO ASI Camera"
            logger.error(msg)
            raise ValueError(msg)

        logger.debug("Looking for ZWO ASI camera with ID '{}'".format(serial_number))

        if not Camera._ids:
            # Not cached camera IDs, need to probe for connected cameras
            n_cameras = Camera._ASIDriver.get_num_of_connected_cameras()
            if n_cameras == 0:
                msg = "No ZWO ASI camera devices found"
                logger.error(msg)
                warn(msg)
                return

            # Get the IDs
            for camera_index in range(n_cameras):
                # Can get IDs without opening cameras by parsing the name string
                self._info = Camera._ASIDriver.get_camera_property(camera_index)
                model, _, id = self._info['name'].partition('(')
                if not id:
                    logger.warning("Found ZWO ASI camera with no ID set")
                    break
                assert id.endswith(')'), self.logger.error("Expected ID enclosed in ()")
                id = id[:-1]
                Camera._ids.append(id)

            logger.debug('Connected ASI ZWO cameras: {}'.format(Camera._ids))

        try:
            self._camera_index = Camera._ids.index(serial_number)
        except ValueError:
            msg = "Could not find ZWO ASI camera with ID '{}'".format(serial_number)
            logger.error(msg)
            warn(msg)
            return
        else:
            logger.debug("Found ZWO ASI Camera with ID '{}' at index {}".format(
                serial_number, self._camera_index))

        if serial_number in Camera._assigned_ids:
            msg = "ZWO ASI Camera with ID '{}' already in use".format(serial_number)
            logger.error(msg)
            warn(msg)
            return

        super().__init__(name, *args, **kwargs)
        self.connect()
        Camera._assigned_ids.append(self.uid)
        if filter_type is not None:
            # connect() will have set this based on camera info, but that doesn't know about filters
            # upstream of the CCD. Can be set manually here, or handled by a filterwheel attribute.
            self._filter_type = filter_type
        if self.is_connected:
            self.logger.info('{} initialised'.format(self))

    def __del__(self):
        """ Attempt some clean up """
        with suppress(AttributeError):
            id = self.uid
            Camera.assigned_ids.remove(id)
            self.logger.debug('Removed {} from assigned IDs list'.format(id))
        with suppress(AttributeError):
            camera_ID = self._camera_ID
            Camera._ASIDriver.close_camera(camera_ID)
            self.logger.debug("Closed ZWO camera {}".format(camera_ID))

    # Properties

    @AbstractCamera.uid.getter
    def uid(self):
        """Return unique identifier for camera.

        Need to overide this because the base class only returns the 1st
        6 characters of the serial number, which is not a unique identifier
        for most of the camera types
        """
        return self._serial_number

    @property
    def image_type(self):
        """ Current camera image type, one of 'RAW8', 'RAW16', 'Y8', 'RGB24' """
        roi_format = Camera._ASIDriver.get_roi_format(self._camera_ID)
        return roi_format['image_type']

    @image_type.setter
    def image_type(self, new_image_type):
        if new_image_type not in self._info['supported_video_format']:
            msg = "Image type '{} not supported by {}".format(new_image_type, self.model)
            self.logger.error(msg)
            raise ValueError(msg)
        roi_format = self._ASIDriver.get_roi_format(self._camera_ID)
        roi_format['image_type'] = new_image_type
        Camera._ASIDriver.set_roi_format(self._camera_ID, **roi_format)

    @property
    def ccd_temp(self):
        """ Current temperature of the camera's image sensor """
        return self._control_getter('TEMPERATURE')[0]

    @property
    def ccd_set_point(self):
        """ Current value of the target temperature for the camera's image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity
        """
        return self._control_getter('TARGET_TEMP')[0]

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        self._control_setter('TARGET_TEMP', set_point)

    @property
    def ccd_cooling_power(self):
        """ Current power level of the camera's image sensor cooling system (as a percentage). """
        return self._control_getter('COOLER_POWER_PERC')[0]

    @property
    def gain(self):
        """ Current value of the camera's gain setting in internal units.

        See `egain` for the corresponding eletrons / ADU value.
        """
        return self._control_getter('GAIN')[0]

    @gain.setter
    def gain(self, gain):
        self._control_setter('GAIN', gain)

    @property
    def egain(self):
        """ Nominal value of the image sensor gain for the camera's current gain setting """
        self._refresh_info()
        return self._info['e_per_adu']

    # Methods

    def __str__(self):
        # ZWO ASI cameras don't have a port so just include the serial number in the string
        # representation.
        s = "{} ({})".format(self.name, self.uid)

        if self.focuser:
            s += ' with {}'.format(self.focuser.name)
            if self.filterwheel:
                s += ' & {}'.format(self.filterwheel.name)
        elif self.filterwheel:
            s += ' with {}'.format(self.filterwheel.name)

        return s

    def connect(self):
        """
        Connect to ZWO ASI camera.

        Gets 'camera_ID' (needed for all driver commands), camera properties and details
        of available camera commands/parameters.
        """
        self.logger.debug("Connecting to {}".format(self))
        self._refresh_info()
        self._camera_ID = self._info['camera_ID']
        self.model, _, _ = self._info['name'].partition('(')
        if self._info['is_colour_camera']:
            self._filter_type = self._info['bayer_pattern']
        else:
            self._filter_type = 'M'

        Camera._ASIDriver.open_camera(self._camera_ID)
        Camera._ASIDriver.init_camera(self._camera_ID)
        self._connected = True

        # Take monochrome 12 bit raw images by default, if we can
        if 'RAW16' in self._info['supported_video_format']:
            self.image_type = 'RAW16'

        self._control_info = Camera._ASIDriver.get_control_caps(self._camera_ID)

    # Private methods

    def _take_exposure(self, seconds, filename, dark, exposure_event, header, *args, **kwargs):
        if not self._exposure_lock.acquire(blocking=False):
            self.logger.warning('Exposure started on {} while one in progress! Waiting.'.format(
                self))
            self._exposure_lock.acquire(blocking=True)

        # Start exposure
        Camera._ASIDriver.start_exposure(self._camera_ID)

        # Start readout thread
        readout_args = (filename,
                        self._info['max_width'],
                        self._info['max_height'],
                        header,
                        exposure_event)
        readout_thread = threading.Timer(interval=seconds.value,
                                         function=self._readout,
                                         args=readout_args)
        readout_thread.start()

    def _readout(self, filename, width, height, header, exposure_event):
        timer = CountdownTimer(duration=self._timeout)
        try:
            exposure_status = Camera._ASIDriver.get_exposure_status(self._camera_ID)
            while exposure_status == 'WORKING':
                if time.expired():
                    msg = "Timeout waiting for exposure on {} to complete".format(self)
                    raise error.Timeout(msg)
                time.sleep(0.01)
                exposure_status = Camera._ASIDriver.get_exposure_status(self._camera_ID)
        except RuntimeError as err:
            # Error returned by driver at some point while polling
            self.logger.error('Error while waiting for exposure on {}: {}'.format(self, err))
            raise err
        else:
            if exposure_status == 'SUCCESS':
                try:
                    image_data = Camera._ASIDriver.get_exposure_data(self._camera_ID,
                                                                     width,
                                                                     height,
                                                                     self.image_type)
                except RuntimeError as err:
                    raise error.PanError('Error getting image data from {}: {}'.format(self, err))
                else:
                    fits_utils.write_fits(image_data, header, filename, self.logger, exposure_event)
            elif exposure_status == 'FAILED':
                raise error.PanError("Exposure failed on {}".format(self))
            elif exposure_status == 'IDLE':
                raise error.PanError("Exposure missing on {}".format(self))
            else:
                raise error.PanError("Unepected exposure status on {}: '{}'".format(
                    self, exposure_status))
        finally:
            exposure_event.set()  # write_fits will have already set this, *if* it got called.
            self._exposure_lock.release()

    def _fits_header(self, seconds, dark):
        header = super()._fits_header(seconds, dark)
        header.set('CAM-GAIN', self.gain, 'Internal units')
        header.set('CAM-BITS', int(get_quantity_value(self._info['bit_depth'], u.bit)),
                   'ADC bit depth')
        header.set('XPIXSZ', get_quantity_value(self._info['pixel_size'], u.um), 'Microns')
        header.set('YPIXSZ', get_quantity_value(self._info['pixel_size'], u.um), 'Microns')
        header.set('EGAIN', get_quantity_value(self.egain, u.electron / u.adu), 'Electrons/ADU')
        return header

    def _refresh_info(self):
        self._info = Camera._ASIDriver.get_camera_property(self._camera_index)

    def _control_getter(self, control_type):
        if control_type in self._control_info.keys():
            return Camera._ASIDriver.get_control_value(self._camera_ID, control_type)
        else:
            raise NotImplementedError("'{}' has no '{}' parameter".format(self.model, control_type))

    def _control_setter(self, control_type, value):
        if control_type not in self._control_info.keys():
            raise NotImplementedError("{} has no '{}'' parameter".format(self.model, control_type))

        control_name = self._control_info[control_type]['name']
        if not self._control_info[control_type]['is_writable']:
            raise NotImplementError("{} cannot set {} parameter'".format(
                self.model, control_name))

        if value != 'AUTO':
            # Check limits.
            max_value = self._control_info[control_type]['max_value']
            if value > max_value:
                msg = "Cannot set {} to {}, clipping to max value {}".format(
                    control_name, value, max_value)
                Camera._ASIDriver.set_control_value(self._camera_ID, control_type, max_value)
                raise error.PanError(msg)

            min_value = self._control_info[control_type]['min_value']
            if value < min_value:
                msg = "Cannot set {} to {}, clipping to min value {}".format(
                    control_name, value, min_value)
                Camera._ASIDriver.set_control_value(self._camera_ID, control_type, min_value)
                raise error.PanError(msg)
        else:
            if not self._control_info[control_type]['is_auto_supported']:
                msg = "{} cannot set {} to AUTO".format(self.model, control_name)
                raise PanError(msg)

        Camera._ASIDriver.set_control_value(self._camera_ID, control_type, value)
