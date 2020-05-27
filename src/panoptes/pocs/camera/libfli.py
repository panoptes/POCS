"""
Low level interface to the FLI library

Reproduces in Python (using ctypes) the C interface provided by FLI's library.
"""
import ctypes
import os

import numpy as np
from astropy import units as u

from panoptes.pocs.camera.sdk import AbstractSDKDriver
from panoptes.pocs.camera import libfliconstants as c
from panoptes.utils import error
from panoptes.utils import get_quantity_value

valid_values = {'interface type': (c.FLIDOMAIN_PARALLEL_PORT,
                                   c.FLIDOMAIN_USB,
                                   c.FLIDOMAIN_SERIAL,
                                   c.FLIDOMAIN_INET,
                                   c.FLIDOMAIN_SERIAL_1200,
                                   c.FLIDOMAIN_SERIAL_19200),
                'device type': (c.FLIDEVICE_CAMERA,
                                c.FLIDEVICE_FILTERWHEEL,
                                c.FLIDEVICE_FOCUSER,
                                c.FLIDEVICE_HS_FILTERWHEEL,
                                c.FLIDEVICE_RAW,
                                c.FLIDEVICE_ENUMERATE_BY_CONNECTION),
                'frame type': (c.FLI_FRAME_TYPE_NORMAL,
                               c.FLI_FRAME_TYPE_DARK,
                               c.FLI_FRAME_TYPE_FLOOD,
                               c.FLI_FRAME_TYPE_RBI_FLUSH)}

################################################################################
# Main SBIGDriver class
################################################################################


class FLIDriver(AbstractSDKDriver):

    def __init__(self, library_path=None, **kwargs):
        """
        Main class representing the FLI library interface. On construction loads
        the shared object/dynamically linked version of the FLI library, which
        must be already installed (see http://www.flicamera.com/software/index.html).
        The current version of the libfli SDK (1.104) only builds a staticly linked
        library by default, the Makefile must be modified to compile a shared object/
        dynamically linked library.

        The name and location of the shared library can be manually specified with
        the library_path argument, otherwise the ctypes.util.find_library function
        will be used to try to locate it.

        Args:
            library_path (str, optional): path to the library, e.g. '/usr/local/lib/libfli.so'.

        Returns:
            `~pocs.camera.libfli.FLIDriver`

        Raises:
            panoptes.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        super().__init__(name='fli', library_path=library_path, **kwargs)

    # Public methods

    def get_SDK_version(self):
        # Get library version.
        version = ctypes.create_string_buffer(64)
        length = ctypes.c_size_t(64)
        self._call_function('getting library version', self._CDLL.FLIGetLibVersion, version, length)
        return version.value.decode('ascii')

    def get_devices(self):
        """Gets currently connected camera info.

        Returns:
            dict: All currently connected camera serial numbers with corresponding device nodes.
        """
        device_list = self.FLIList(interface_type=c.FLIDOMAIN_USB,
                                   device_type=c.FLIDEVICE_CAMERA)
        if not device_list:
            raise error.PanError("No FLI camera devices found.")

        cameras = {}
        for device in device_list:
            port = device[0]
            try:
                handle = self.FLIOpen(port)
            except RuntimeError as err:
                self.logger.error("Couldn't open FLI camera at {}: {}".format(port, err))
            else:
                try:
                    serial_number = self.FLIGetSerialString(handle)
                except RuntimeError as err:
                    self.logger.error("Couldn't get serial number from FLI camera at {}: {}".format(
                        port, err))
                else:
                    cameras[serial_number] = port
            finally:
                self.FLIClose(handle)

        return cameras

    def FLIList(self, interface_type=c.FLIDOMAIN_USB, device_type=c.FLIDEVICE_CAMERA):
        """
        List available devices.

        This function returns a list of available FLI devices, including the device port
        and model name.

        Args:
            interface_type (int, optional): interface to search for connected devices. Valid values
                are libfli.FLIDOMAIN_USB (default), FLIDOMAIN_PARALLEL_PORT, FLIDOMAIN_SERIAL,
                FLIDOMAIN_SERIAL_1200, FLIDOMAIN_SERIAL_19200, FLIDOMAIN_INET.
            device_types (int, optional): device type to search for. Valid values are
                libfli.FLIDEVICE_CAMERA (default), FLIDEVICE_FILTERWHEEL, FLIDEVICE_HS_FILTERWHEEL,
                FLIDEVICE_FOCUSER, FLIDEVICE_ENUMERATE_BY_CONNECTION, FLIDEVICE_RAW.

        Returns:
            list of tuples: (port, model name) for each available device
        """
        domain = 0x0000 | self._check_valid(interface_type, 'interface type')
        domain = domain | self._check_valid(device_type, 'device type')

        names = ctypes.POINTER(ctypes.c_char_p)()
        self._call_function('getting device list', self._CDLL.FLIList,
                            ctypes.c_long(domain), ctypes.byref(names))

        available_devices = []
        for name in names:
            if name is None:
                break
            available_devices.append(name.decode('ascii').split(';'))

        # Call FLIFreeList to clean up
        self._call_function('freeing device list', self._CDLL.FLIFreeList, names)

        return available_devices

    def FLIOpen(self, port, interface_type=c.FLIDOMAIN_USB, device_type=c.FLIDEVICE_CAMERA):
        """
        Get a handle to an FLI device.

        This function requires the port, interface type and device type of the requested device.
        Valid ports can be obtained with the FLIList() method.

        Args:
            port (str): port that the device is connected to, e.g. /dev/fliusb0
            interface_type (int, optional): interface type of the requested device. Valid values are
                libfli.FLIDOMAIN_USB (default), FLIDOMAIN_PARALLEL_PORT, FLIDOMAIN_SERIAL,
                FLIDOMAIN_SERIAL_1200, FLIDOMAIN_SERIAL_19200, FLIDOMAIN_INET.
            device_type (int, optional): device type of the requested device. Valid values are
                libfli.FLIDEVICE_CAMERA (default), FLIDEVICE_FILTERWHEEL, FLIDEVICE_HS_FILTERWHEEL,
                FLIDEVICE_FOCUSER, FLIDEVICE_ENUMERATE_BY_CONNECTION, FLIDEVICE_RAW.

        Returns:
            ctypes.c_long: an opaque handle used by library functions to refer to FLI hardware
        """
        domain = 0x0000 | self._check_valid(interface_type, 'interface type')
        domain = domain | self._check_valid(device_type, 'device type')

        handle = ctypes.c_long()

        self._call_function('getting handle', self._CDLL.FLIOpen,
                            ctypes.byref(handle), port.encode('ascii'), ctypes.c_long(domain))

        return handle

    def FLIClose(self, handle):
        """
        Close a handle to an FLI device.

        Args:
            handle (ctypes.c_long): handle to close
        """
        self._call_function('closing handle', self._CDLL.FLIClose, handle)

    def FLIGetModel(self, handle):
        """
        Get the model of a given device.

        Args:
            handle (ctypes.c_long): handle of the device to get the model of.

        Returns:
            string: model of the device
        """
        model = ctypes.create_string_buffer(64)
        length = ctypes.c_size_t(64)
        self._call_function('getting model', self._CDLL.FLIGetModel, handle,
                            model, length)
        return model.value.decode('ascii')

    def FLIGetSerialString(self, handle):
        """
        Get the serial string of a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera device to get the serial strong of.

        Returns:
            string: serial string of the camera
        """
        serial_string = ctypes.create_string_buffer(64)
        length = ctypes.c_size_t(64)
        self._call_function('getting serial string', self._CDLL.FLIGetSerialString, handle,
                            serial_string, length)
        return serial_string.value.decode('ascii')

    def FLIGetFWRevision(self, handle):
        """
        Get firmware revision of a given device

        Args:
            handle (ctypes.c_long): handle of the camera device to get the firmware revision of.

        Returns:
            int: firmware revision of the camera
        """
        fwrev = ctypes.c_long()
        self._call_function('getting firmware revision', self._CDLL.FLIGetFWRevision, handle,
                            ctypes.byref(fwrev))
        return fwrev.value

    def FLIGetHWRevision(self, handle):
        """
        Get hardware revision of a given device

        Args:
            handle (ctypes.c_long): handle of the camera device to get the hardware revision of.

        Returns:
            int: hardware revision of the cameras
        """
        hwrev = ctypes.c_long()
        self._call_function('getting hardware revision', self._CDLL.FLIGetHWRevision, handle,
                            ctypes.byref(hwrev))
        return hwrev.value

    def FLIGetPixelSize(self, handle):
        """
        Get the dimensions of a pixel in the array of a given device.

        Args:
            handle (ctypes.c_long): handle of the device to find the pixel size of.

        Returns:
            astropy.units.Quantity: (x, y) dimensions of a pixel.
        """
        pixel_x = ctypes.c_double()
        pixel_y = ctypes.c_double()
        self._call_function('getting pixel size', self._CDLL.FLIGetPixelSize, handle,
                            ctypes.byref(pixel_x), ctypes.byref(pixel_y))
        return ((pixel_x.value, pixel_y.value) * u.m).to(u.um)

    def FLIGetTemperature(self, handle):
        """
        Get the temperature of a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera device to get the temperature of.

        Returns:
            astropy.units.Quantity: temperature of the camera cold finger in degrees Celsius
        """
        temperature = ctypes.c_double()
        self._call_function('getting temperature', self._CDLL.FLIGetTemperature,
                            handle, ctypes.byref(temperature))
        return temperature * u.Celsius

    def FLISetTemperature(self, handle, temperature):
        """
        Set the temperature of a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera device to set the temperature of.
            temperature (astropy.units.Quantity): temperature to set the cold finger of the camera
                to. A simple numeric type can be given instead of a Quantity, in which case the
                units are assumed to be degrees Celsius.
        """
        temperature = get_quantity_value(temperature, unit=u.Celsius)
        temperature = ctypes.c_double(temperature)

        self._call_function('setting temperature', self._CDLL.FLISetTemperature,
                            handle, temperature)

    def FLIGetCoolerPower(self, handle):
        """
        Get the cooler power level for a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera to get the cooler power of.

        Returns:
            float: cooler power, in percent.
        """
        power = ctypes.c_double()
        self._call_function('getting cooler power', self._CDLL.FLIGetCoolerPower,
                            handle, ctypes.byref(power))
        return power.value * u.percent

    def FLISetExposureTime(self, handle, exposure_time):
        """
        Set the exposure time for a camera.

        Args:
            handle (ctypes.c_long): handle of the camera to set the exposure time of.
            exposure_time (u.Quantity): required exposure time. A simple numeric type
                can be given instead of a Quantity, in which case the units are assumed
                to be seconds.
        """
        exposure_time = get_quantity_value(exposure_time, unit=u.second)
        milliseconds = ctypes.c_long(int(exposure_time * 1000))
        self._call_function('setting exposure time', self._CDLL.FLISetExposureTime,
                            handle, milliseconds)

    def FLISetFrameType(self, handle, frame_type):
        """
        Set the frame type for a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera to set the frame type of.
            frame_type (int): frame type. Valid values are libfli.FLI_FRAME_TYPE_NORMAL,
            FLI_FRAME_TYPE_DARK, FLI_FRAME_TYPE_FLOOD, FLI_FRAME_TYPE_RBI_FLUSH.
        """
        frame_type = self._check_valid(frame_type, 'frame type')
        self._call_function('setting frame type', self._CDLL.FLISetFrameType,
                            handle, ctypes.c_long(frame_type))

    def FLIGetArrayArea(self, handle):
        """
        Get the array area of the give camera.

        This function finds the total area of the CCD array for a given camera. This area is
        specified in terms of an upper left point and a lower right point.

        Args:
            handle (ctypes.c_long): handle of the camera to get the array area of.
        """
        upper_left_x = ctypes.c_long()
        upper_left_y = ctypes.c_long()
        lower_right_x = ctypes.c_long()
        lower_right_y = ctypes.c_long()
        self._call_function('getting array area', self._CDLL.FLIGetArrayArea, handle,
                            ctypes.byref(upper_left_x), ctypes.byref(upper_left_y),
                            ctypes.byref(lower_right_x), ctypes.byref(lower_right_y))
        return ((upper_left_x.value, upper_left_y.value),
                (lower_right_x.value, lower_right_y.value))

    def FLIGetVisibleArea(self, handle):
        """
        Get the visible array area of the give camera.

        This function finds the visible area of the CCD array for a given camera. This area is
        specified in terms of an upper left point and a lower right point.

        Args:
            handle (ctypes.c_long): handle of the camera to get the array area of.
        """
        upper_left_x = ctypes.c_long()
        upper_left_y = ctypes.c_long()
        lower_right_x = ctypes.c_long()
        lower_right_y = ctypes.c_long()
        self._call_function('getting visible area', self._CDLL.FLIGetVisibleArea, handle,
                            ctypes.byref(upper_left_x), ctypes.byref(upper_left_y),
                            ctypes.byref(lower_right_x), ctypes.byref(lower_right_y))
        return ((upper_left_x.value, upper_left_y.value),
                (lower_right_x.value, lower_right_y.value))

    def FLISetImageArea(self, handle, upper_left, lower_right):
        """
        Set the image area for a given camera.

        This function sets the image area to an area specified in terms of an upperleft point and
        a lower right point. Note that the lower right point coordinate must take into account
        the horizontal and vertical bin factor setttings, but the upper left coordinate is
        absolute.

        Args:
            handle (ctypes.c_long): handle of the camera to set the image area of.
            upper_left (int, int): (x, y) coordinate of upper left point
            lower_right (int, int): (x, y) coordinate of lower right point
        """
        self._call_function('setting image area', self._CDLL.FLISetImageArea, handle,
                            ctypes.c_long(upper_left[0]), ctypes.c_long(upper_left[1]),
                            ctypes.c_long(lower_right[0]), ctypes.c_long(lower_right[1]))

    def FLISetHBin(self, handle, bin_factor):
        """
        Set the horizontal bin factor for a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera to set the horizontal bin factor for.
            bin_factor (int): horizontal bin factor. The valid range is from 1 to 16 inclusive.
        """
        if bin_factor < 1 or bin_factor > 16:
            raise ValueError("bin_factor must be in the range 1 to 16, got {}!".format(bin_factor))
        self._call_function('setting horizontal bin factor', self._CDLL.FLISetHBin,
                            handle, ctypes.c_long(bin_factor))

    def FLISetVBin(self, handle, bin_factor):
        """
        Set the vertical bin factor for a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera to set the vertical bin factor for.
            bin_factor (int): vertical bin factor. The valid range is from 1 to 16 inclusive.
        """
        if bin_factor < 1 or bin_factor > 16:
            raise ValueError("bin factor must be in the range 1 to 16, got {}!".format(bin_factor))
        self._call_function('setting vertical bin factor', self._CDLL.FLISetVBin,
                            handle, ctypes.c_long(bin_factor))

    def FLISetNFlushes(self, handle, n_flushes):
        """
        Set the number of flushes for a given camera.

        This function sets the number of the times the CCD array of the camera is flushed before
        exposing a frame. Some FLI cameras support background flishing. Background flushing
        continuously flushes the CCD eliminating the need for pre-exposure flushings.

        Args:
            handle (ctypes.c_long): handle of the camera to set the number of flushes for.
            n_flushes (int): number of times to flush the CCD array before an exposure. The valid
                range is from 0 to 16 inclusive.
        """
        if n_flushes < 0 or n_flushes > 16:
            raise ValueError("n_flishes must be in the range 0 to 16, got {}!".format(n_flushes))
        self._call_function('setting number of flushes', self._CDLL.FLISetNFlushes,
                            handle, ctypes.c_long(n_flushes))

    def FLIExposeFrame(self, handle):
        """
        Expose a frame for a given camera.

        This function exposes a frame according the settings (image area, exposure time, binning,
        etc.) of the camera. The settings must have been previously set to valid values using
        the appropriate FLISet* methods. This function is non-blocking and returns once the
        exposure has stated.

        Args:
            handle (ctypes.c_long): handle of the camera to start the exposure on.
        """
        self._call_function('starting exposure', self._CDLL.FLIExposeFrame, handle)

    def FLIGetExposureStatus(self, handle):
        """
        Get the remaining exposure time of a given camera.

        Args:
            handle (ctypes.c_long): handle of the camera to get the remaining exposure time of.

        Returns:
            astropy.units.Quantity: remaining exposure time
        """
        time_left = ctypes.c_long()
        self._call_function('getting exposure status', self._CDLL.FLIGetExposureStatus,
                            handle, ctypes.byref(time_left))
        return (time_left.value * u.ms).to(u.s)

    def FLIGrabRow(self, handle, width):
        """
        Grabs a row of image data from a given camera.

        This function grabs the next available row of imae data from the specificed camera and
        returns it as a nupt array. The widht of the row must be specified. The width should be
        consistent with the call to FLISetImageArea() that preceded the call to FLIExposeFrame().
        This function should not be called until the exposure is complete, which can be confirmed
        with FLIGetExposureStatus.

        Args:
            handle (ctypes.c_long): handle of the camera to grab a row from.
            width (int): width of the image row in pixelStart

        Returns:
            numpy.ndarray: row of image data
        """
        row_data = np.zeros(width, dtype=np.uint16)
        self._call_function('grabbing row', self._CDLL.FLIGrabRow,
                            handle,
                            row_data.ctypes.data_as(ctypes.c_void_p),
                            ctypes.c_size_t(row_data.nbytes))
        return row_data

    def FLIGrabFrame(self, handle, width, height):
        """
        Grabs an image frame from a given camera.

        This function grabs the entire image frame from the specified camera and returns it as a
        numpy array. The width and height of the image must be specified. The width and height
        should be consistent with the call to FLISetImageArea() that preceded the call to
        FLIExposeFrame(). This function should not be called until the exposure is complete, which
        can be confirmed with FLIGetExposureStatus().

        Args:
            handle (ctypes.c_long): handle of the camera to grab a frame from.
            width (int): width of the image frame in pixels
            height (int): height of the image frame in pixels

        Returns:
            numpy.ndarray: image from the camera
        """
        image_data = np.zeros((height, width), dtype=np.uint16, order='C')
        bytes_grabbed = ctypes.c_size_t()
        self._call_function('grabbing frame', self._CDLL.FLIGrabFrame,
                            handle,
                            image_data.ctypes.data_as(ctypes.c_void_p),
                            ctypes.c_size_t(image_data.nbytes),
                            ctypes.byref(bytes_grabbed))

        if bytes_grabbed.value != image_data.nbytes:
            self.logger.error('FLI camera readout error: expected {} bytes, got {}!'.format(
                image_data.nbytes, bytes_grabbed.value
            ))

        return image_data

    # Private methods

    def _call_function(self, name, function, *args, **kwargs):
        error_code = function(*args, *kwargs)
        if error_code != 0:
            # FLI library functions return the negative of OS error codes.
            raise RuntimeError("Error {}: '{}' (OS error {})".format(name,
                                                                     os.strerror(-error_code),
                                                                     -error_code))

    def _check_valid(self, value, name):
        if value not in valid_values[name]:
            raise ValueError("Got invalid {}, {}!".format(name, value))
        return value
