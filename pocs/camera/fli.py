import time
import re
from warnings import warn
from threading import Event
from threading import Timer
from threading import Lock
from contextlib import suppress

import numpy as np

from astropy import units as u

from pocs.camera.camera import AbstractCamera
from pocs.camera import libfli
from pocs.camera import libfliconstants as c
from pocs.utils.images import fits as fits_utils
from pocs.utils.logger import get_root_logger

# FLI camera serial numbers have pairs of letters followed by a sequence of numbers
serial_number_pattern = re.compile(r'^(ML|PL|KL|HP)\d+$')


class Camera(AbstractCamera):

    # Class variable to cache the device node scanning results
    _fli_nodes = None

    # Class variable to store the device nodes already in use. Prevents scanning known Birgers &
    # acts as a check against Birgers assigned to incorrect ports.
    _assigned_nodes = []

    def __init__(self,
                 name='FLI Camera',
                 set_point=25 * u.Celsius,
                 filter_type='M',
                 library_path=None,
                 *args, **kwargs):
        # FLI cameras should be specified by either serial number (preferred) or 'port' (device
        # node). For backwards compatibility reasons allow port to be used as an alias of serial
        # number. If both are given serial number takes precedence
        kwargs['readout_time'] = kwargs.get('readout_time', 1.0)
        kwargs['file_extension'] = 'fits'

        # Create a Lock that will be used to prevent overlapping exposures.
        self._exposure_lock = Lock()

        # Create an instance of the FLI Driver interface
        self._FLIDriver = libfli.FLIDriver(library_path)

        # Would usually use self.logger but that won't exist until after calling super().__init__(),
        # and don't want to do that until after the serial number and port have both been determined
        # in order to avoid log entries with misleading values. To enable logging during the device
        # scanning phase use get_root_logger() instead.
        logger = get_root_logger()

        if kwargs.get('serial_number') or serial_number_pattern.match(kwargs.get('port')):
            # Have been given a serial number instead of a device node
            kwargs['serial_number'] = kwargs.get('serial_number', kwargs.get('port'))
            logger.debug('Looking for {} ({})...'.format(name, kwargs['serial_number']))

            if Camera._fli_nodes is None:
                # No cached device nodes scanning results. 1st get list of all FLI cameras
                logger.debug('Getting serial numbers for all connected FLI cameras')
                Camera._fli_nodes = {}
                device_list = self._FLIDriver.FLIList(interface_type=c.FLIDOMAIN_USB,
                                                      device_type=c.FLIDEVICE_CAMERA)
                if not device_list:
                    message = 'No FLI camera devices found!'
                    logger.error(message)
                    warn(message)
                    return

                # Get serial numbers for all connected FLI cameras
                for device in device_list:
                    handle = self._FLIDriver.FLIOpen(port=device[0])
                    serial_number = self._FLIDriver.FLIGetSerialString(handle)
                    self._FLIDriver.FLIClose(handle)
                    Camera._fli_nodes[serial_number] = device[0]
                logger.debug('Connected FLI cameras: {}'.format(Camera._fli_nodes))

            # Search in cached device node scanning results for serial number.
            try:
                device_node = Camera._fli_nodes[kwargs['serial_number']]
            except KeyError:
                message = 'Could not find {} ({})!'.format(name, kwargs['serial_number'])
                logger.error(message)
                warn(message)
                return
            logger.debug('Found {} ({}) on {}'.format(
                name, kwargs['serial_number'], device_node))
            kwargs['port'] = device_node

        if kwargs['port'] in Camera._assigned_nodes:
            message = 'Device node {} already in use!'.format(kwargs['port'])
            logger.error(message)
            warn(message)
            return

        super().__init__(name, *args, **kwargs)
        self.connect()
        Camera._assigned_nodes.append(self.port)
        self.filter_type = filter_type

        if self.is_connected:
            self.ccd_set_point = set_point
            self.logger.info('{} initialised'.format(self))

    def __del__(self):
        with suppress(AttributeError):
            device_node = self.port
            Camera._assigned_nodes.remove(device_node)
            self.logger.debug('Removed {} from assigned nodes list'.fomat(device_node))
        with suppress(AttributeError):
            handle = self._handle
            self._FLIDriver.FLIClose(handle)
            self.logger.debug('Closed FLI camera handle {}'.format(handle.value))

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
    def ccd_temp(self):
        """
        Current temperature of the camera's image sensor.
        """
        return self._FLIDriver.FLIGetTemperature(self._handle)

    @property
    def ccd_set_point(self):
        """
        Current value of the CCD set point, the target temperature for the camera's
        image sensor cooling control.

        Can be set by assigning an astropy.units.Quantity.
        """
        return self._set_point

    @ccd_set_point.setter
    def ccd_set_point(self, set_point):
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        self._FLIDriver.FLISetTemperature(self._handle, set_point)
        if isinstance(set_point, u.Quantity):
            self._set_point = set_point
        else:
            self._set_point = set_point * u.Celsius

    @property
    def ccd_cooling_enabled(self):
        """
        Current status of the camera's image sensor cooling system (enabled/disabled).

        Note: For FLI cameras this is always True, and cannot be set.
        """
        return True

    @ccd_cooling_enabled.setter
    def ccd_cooling_enabled(self, enabled):
        raise NotImplementedError('Cannot disable cooling on FLI cameras')

    @property
    def ccd_cooling_power(self):
        """
        Current power level of the camera's image sensor cooling system (as
        a percentage of the maximum).
        """
        return self._FLIDriver.FLIGetCoolerPower(self._handle)

    @property
    def properties(self):
        """ A collection of camera properties as read from the camera """
        return self._info

# Methods

    def connect(self):
        """
        Connect to FLI camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to {} on {}'.format(self.name, self.port))

        # Get handle from the SBIGDriver.
        self._handle = self._FLIDriver.FLIOpen(port=self.port)
        if self._handle == c.FLI_INVALID_DEVICE:
            message = 'Could not connect to {} on {}!'.format(self.name, self.port)
            self.logger.error(message)
            warn(message)
            self._connected = False
            return

        self._connected = True
        self._get_camera_info()
        self._serial_number = self._info['serial number']
        self.model = self._info['camera model']
        self.logger.debug("{} connected".format(self))

# Private Methods

    def _take_exposure(self, seconds, filename, dark, exposure_event, header, *args, **kwargs):
        if not self._exposure_lock.acquire(blocking=False):
            self.logger.warning('Exposure started on {} while one in progress! Waiting.'.format(
                self))
            self._exposure_lock.acquire(blocking=True)

        self._FLIDriver.FLISetExposureTime(self._handle, exposure_time=seconds)

        if dark:
            frame_type = c.FLI_FRAME_TYPE_DARK
        else:
            frame_type = c.FLI_FRAME_TYPE_NORMAL
        self._FLIDriver.FLISetFrameType(self._handle, frame_type)

        # For now set to 'visible' (i.e. light sensitive) area of image sensor.
        # Can later use this for windowed exposures.
        self._FLIDriver.FLISetImageArea(self._handle,
                                        self._info['visible corners'][0],
                                        self._info['visible corners'][1])

        # No on chip binning for now.
        self._FLIDriver.FLISetHBin(self._handle, bin_factor=1)
        self._FLIDriver.FLISetVBin(self._handle, bin_factor=1)

        # No pre-exposure image sensor flushing, either.
        self._FLIDriver.FLISetNFlushes(self._handle, n_flushes=0)

        # In principle can set bit depth here (16 or 8 bit) but most FLI cameras don't support it.
        # Leave alone for now.

        # Start exposure
        self._FLIDriver.FLIExposeFrame(self._handle)

        # Start readout thread
        readout_args = (filename,
                        self._info['visible width'],
                        self._info['visible height'],
                        header,
                        exposure_event)
        readout_thread = Timer(interval=self._FLIDriver.FLIGetExposureStatus(self._handle).value,
                               function=self._readout,
                               args=readout_args)
        readout_thread.start()

    def _readout(self, filename, width, height, header, exposure_event):

        # Wait for exposure to complete. This should have a timeout in case something goes wrong.
        while self._FLIDriver.FLIGetExposureStatus(self._handle) > 0 * u.second:
            time.sleep(self._FLIDriver.FLIGetExposureStatus(self._handle).value)

        # Readout.
        # Use FLIGrabRow for now at least because I can't get FLIGrabFrame to work.
        # image_data = self._FLIDriver.FLIGrabFrame(self._handle, width, height)
        image_data = np.zeros((height, width), dtype=np.uint16)
        for i in range(image_data.shape[0]):
            try:
                image_data[i] = self._FLIDriver.FLIGrabRow(self._handle, image_data.shape[1])
            except RuntimeError as err:
                message = 'Readout error: expected {} rows, got {}!'.format(image_data.shape[0], i)
                self.logger.error(message)
                self.logger.error(err)
                warn(message)
                break

        fits_utils.write_fits(image_data, header, filename, self.logger, exposure_event)
        self._exposure_lock.release()

    def _fits_header(self, seconds, dark):
        header = super()._fits_header(seconds, dark)

        header.set('CAM-HW', self._info['hardware version'], 'Camera hardware version')
        header.set('CAM-FW', self._info['firmware version'], 'Camera firmware version')
        header.set('XPIXSZ', self._info['pixel width'].value, 'Microns')
        header.set('YPIXSZ', self._info['pixel height'].value, 'Microns')

        return header

    def _get_camera_info(self):

        serial_number = self._FLIDriver.FLIGetSerialString(self._handle)
        camera_model = self._FLIDriver.FLIGetModel(self._handle)
        hardware_version = self._FLIDriver.FLIGetHWRevision(self._handle)
        firmware_version = self._FLIDriver.FLIGetFWRevision(self._handle)

        pixel_width, pixel_height = self._FLIDriver.FLIGetPixelSize(self._handle)
        ccd_corners = self._FLIDriver.FLIGetArrayArea(self._handle)
        visible_corners = self._FLIDriver.FLIGetVisibleArea(self._handle)

        self._info = {
            'serial number': serial_number,
            'camera model': camera_model,
            'hardware version': hardware_version,
            'firmware version': firmware_version,
            'pixel width': pixel_width,
            'pixel height': pixel_height,
            'array corners': ccd_corners,
            'array height': ccd_corners[1][1] - ccd_corners[0][1],
            'array width': ccd_corners[1][0] - ccd_corners[0][0],
            'visible corners': visible_corners,
            'visible height': visible_corners[1][1] - visible_corners[0][1],
            'visible width': visible_corners[1][0] - visible_corners[0][0]
        }
