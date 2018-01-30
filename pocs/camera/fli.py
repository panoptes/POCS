import time
import os
import re
from warnings import warn
from threading import Event
from threading import Timer
from threading import Lock

import numpy as np

from astropy import units as u
from astropy.io import fits

from pocs.camera.camera import AbstractCamera
from pocs.camera import libfli
from pocs.utils.images import fits as fits_utils

# FLI camera serial numbers have pairs of letters followed by a sequence of numbers
serial_number_pattern = re.compile('^(ML|PL|KL|HP)\d+$')


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
                 *args, **kwargs):
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)

        # Create a Lock that will be used to prevent overlapping exposures.
        self._exposure_lock = Lock()

        # Create an instance of the FLI Driver interface
        self._FLIDriver = libfli.FLIDriver()

        if serial_number_pattern.match(self.port):
            # Have been given a serial number instead of a device node
            self.logger.debug('Looking for {} ({})...'.format(self.name, self.port))

            if Camera._fli_nodes is None:
                # No cached device nodes scanning results. 1st get list of all FLI cameras
                self.logger.debug('Getting serial numbers for all connected FLI cameras')
                Camera._fli_nodes = {}
                device_list = self._FLIDriver.FLIList(interface_type=libfli.FLIDOMAIN_USB,
                                                      device_type=libfli.FLIDEVICE_CAMERA)
                if not device_list:
                    message = 'No FLI camera devices found!'
                    self.logger.error(message)
                    warn(message)
                    return

                # Get serial numbers for all connected FLI cameras
                for device in device_list:
                    handle = self._FLIDriver.FLIOpen(port=device[0])
                    serial_number = self._FLIDriver.FLIGetSerialString(handle)
                    self._FLIDriver.FLIClose(handle)
                    Camera._fli_nodes[serial_number] = device[0]
                self.logger.debug('Connected FLI cameras: {}'.format(Camera._fli_nodes))

            # Search in cached device node scanning results for serial number.
            try:
                device_node = Camera._fli_nodes[self.port]
            except KeyError:
                message = 'Could not find {} ({})!'.format(self.name, self.port)
                self.logger.error(message)
                warn(message)
                return
            self.logger.debug('Found {} ({}) on {}'.format(self.name, self.port, device_node))
            self.port = device_node

        if self.port in Camera._assigned_nodes:
            message = 'Device node {} already in use!'.format(self.port)
            self.logger.error(message)
            warn(message)
            return

        self.connect()
        Camera._assigned_nodes.append(self.port)
        self.filter_type = filter_type

        if self.is_connected:
            self.ccd_set_point = set_point
            self.logger.info('{} initialised'.format(self))

    def __del__(self):
        try:
            device_node = self.port
            Camera._assigned_nodes.remove(device_node)
            self.logger.debug('Removed {} from assigned nodes list'.fomat(device_node))
        except AttributeError:
            pass
        try:
            handle = self._handle
            self._FLIDriver.FLIClose(handle)
            self.logger.debug('Closed FLI camera handle {}'.format(handle.value))
        except AttributeError:
            pass

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
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

# Methods

    def connect(self):
        """
        Connect to FLI camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to {} on {}'.format(self.name, self.port))

        # Get handle from the SBIGDriver.
        self._handle = self._FLIDriver.FLIOpen(port=self.port)
        if self._handle == libfli.FLI_INVALID_DEVICE:
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

    def take_exposure(self,
                      seconds=1.0 * u.second,
                      filename=None,
                      dark=False,
                      blocking=False,
                      *args,
                      **kwargs):
        """
        Take an exposure for given number of seconds and saves to provided filename.

        Args:
            seconds (u.second, optional): Length of exposure
            filename (str, optional): Image is saved to this filename
            dark (bool, optional): Exposure is a dark frame (don't open shutter), default False
            blocking (bool, optional): If False (default) returns immediately after starting
                the exposure, if True will block until it completes.

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

        if not self._exposure_lock.acquire(blocking=False):
            message = 'Attempt to start exposure on {} ({}) while exposure in progress! Waiting...'.format(self.name, self.uid)
            self.logger.warning(message)
            warn(message)
            self._exposure_lock.acquire(blocking=True)

        self.logger.debug('Taking {} exposure on {}: {}'.format(seconds, self.name, filename))

        self._FLIDriver.FLISetExposureTime(self._handle, exposure_time=seconds)

        if dark:
            frame_type = libfli.FLI_FRAME_TYPE_DARK
        else:
            frame_type = libfli.FLI_FRAME_TYPE_NORMAL
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

        # Build FITS header
        header = self._fits_header(seconds, dark)

        # Start exposure
        self._FLIDriver.FLIExposeFrame(self._handle)

        # Start readout thread
        exposure_event = Event()
        readout_args = (filename,
                        self._info['visible width'],
                        self._info['visible height'],
                        header,
                        exposure_event)
        readout_thread = Timer(interval=self._FLIDriver.FLIGetExposureStatus(self._handle).value,
                               function=self._readout,
                               args=readout_args)
        readout_thread.start()

        if blocking:
            exposure_event.wait()

        return exposure_event

# Private Methods

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

        self._exposure_lock.release()

        fits_utils.write_fits(image_data, header, filename, self.logger, exposure_event)

    def _fits_header(self, seconds, dark):
        header = super()._fits_header(seconds, dark)

        header.set('CAM-HW', self._info['hardware version'], 'Camera hardware version')
        header.set('CAM-FW', self._info['firmware version'], 'Camera firmware version')
        header.set('XPIXSZ', self._info['pixel width'].value, 'Microns')
        header.set('YPIXSZ', self._info['pixel height'].value, 'Microns')

        if self.focuser:
            header = self.focuser._fits_header(header)

        return header

    def _get_camera_info(self):
        self._info = {}
        self._info['serial number'] = self._FLIDriver.FLIGetSerialString(self._handle)
        self._info['camera model'] = self._FLIDriver.FLIGetModel(self._handle)
        self._info['hardware version'] = self._FLIDriver.FLIGetHWRevision(self._handle)
        self._info['firmware version'] = self._FLIDriver.FLIGetFWRevision(self._handle)
        self._info['pixel width'], self._info['pixel height'] = self._FLIDriver.FLIGetPixelSize(self._handle)
        self._info['array corners'] = self._FLIDriver.FLIGetArrayArea(self._handle)
        self._info['array height'] = self._info['array corners'][1][1] - self._info['array corners'][0][1]
        self._info['array width'] = self._info['array corners'][1][0] - self._info['array corners'][0][0]
        self._info['visible corners'] = self._FLIDriver.FLIGetVisibleArea(self._handle)
        self._info['visible height'] = self._info['visible corners'][1][1] - self._info['visible corners'][0][1]
        self._info['visible width'] = self._info['visible corners'][1][0] - self._info['visible corners'][0][0]
