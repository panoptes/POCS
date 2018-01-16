import time
import os
from threading import Event
from threading import Timer

import numpy as np

from astropy import units as u
from astropy.io import fits

from pocs.camera.camera import AbstractCamera
from pocs.camera import libfli
from pocs.utils.images import fits as fits_utils


class Camera(AbstractCamera):

    def __init__(self,
                 name='FLI Camera',
                 set_point=None,
                 filter_type='M',
                 *args, **kwargs):
        kwargs['readout_time'] = 1.0
        kwargs['file_extension'] = 'fits'
        super().__init__(name, *args, **kwargs)

        # Create an instance of the FLI Driver interface
        self._FLIDriver = libfli.FLIDriver()
        self.connect()

        self.filter_type = filter_type

        if self.is_connected:
            if set_point is not None:
                # Set cooling
                self.CCD_set_point = set_point
            else:
                self._set_point = None
            self.logger.info('{} initialised'.format(self))

# Properties

    @AbstractCamera.uid.getter
    def uid(self):
        # Unlike Canon DSLRs 1st 6 characters of serial number is *not* a unique identifier.
        # Need to use the whole thing.
        return self._serial_number

    @property
    def CCD_temp(self):
        return self._FLIDriver.FLIGetTemperature(self._handle)

    @property
    def CCD_set_point(self):
        return self._set_point

    @CCD_set_point.setter
    def CCD_set_point(self, set_point):
        self.logger.debug("Setting {} cooling set point to {}".format(self.name, set_point))
        self._FLIDriver.FLISetTemperature(self._handle, set_point)
        if isinstance(set_point, u.Quantity):
            self._set_point = set_point
        else:
            self._set_point = set_point * u.Celsius

    @property
    def CCD_cooling_power(self):
        return self._FLIDriver.FLIGetCoolerPower(self._handle)

# Methods

    def connect(self):
        """
        Connect to FLI camera.

        Gets a 'handle', serial number and specs/capabilities from the driver
        """
        self.logger.debug('Connecting to camera {}'.format(self.uid))

        # Get handle from the SBIGDriver.
        self._handle = self._FLIDriver.FLIOpen(port=self.port)
        self.logger.debug("{} connected".format(self.name))
        self._connected = True
        self._get_camera_info()
        self._serial_number = self._info['serial number']
        self.model = self._info['camera model']

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

        Returns:
            threading.Event: Event that will be set when exposure is complete

        """
        assert self.is_connected, self.logger.error("Camera must be connected for take_exposure!")

        assert filename is not None, self.logger.warning("Must pass filename for take_exposure")

        if not isinstance(seconds, u.Quantity):
            seconds = seconds * u.second

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
                self.logger.error('FLI camera readout error: expected {} rows, got {}!'.format(
                    image_data.shape[0], i
                ))
                self.logger.error(err)
                break

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
