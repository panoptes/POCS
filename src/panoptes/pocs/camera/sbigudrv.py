"""
Low level interface to the SBIG Unversal Driver/Library.

Reproduces in Python (using ctypes) the C interface provided by SBIG's shared
library, i.e. 1 function that does 72 different things selected by passing an
integer as the first argument. This is basically a direct translation of the
enums and structs defined in the library C-header to Python dicts and
ctypes.Structures, plus a class (SBIGDriver) to load the library
and call the single command function (SBIGDriver._send_command()).
"""
import ctypes
import time
import threading
import enum

import numpy as np
from numpy.ctypeslib import as_ctypes
from astropy import units as u

from panoptes.pocs.camera.sdk import AbstractSDKDriver
from panoptes.utils import error
from panoptes.utils import CountdownTimer
from panoptes.utils import get_quantity_value

################################################################################
# Main SBIGDriver class
################################################################################


class SBIGDriver(AbstractSDKDriver):

    def __init__(self, library_path=None, retries=1, **kwargs):
        """
        Main class representing the SBIG Universal Driver/Library interface.
        On construction loads SBIG's shared library which must have already
        been installed (see http://archive.sbig.com/sbwhtmls/devsw.htm). The
        name and location of the shared library can be manually specified with
        the library_path argument, otherwise the ctypes.util.find_library function
        will be used to locate it.

        Args:
            library_path (str, optional): path to the library e.g. '/usr/local/lib/libsbigudrv.so'.
            retries (int, optional): maximum number of times to attempt to send
                a command to a camera in case of failures. Default 1, i.e. only
                send a command once.

        Returns:
            `~pocs.camera.sbigudrv.SBIGDriver`

        Raises:
            panoptes.utils.error.NotFound: raised if library_path not given & find_libary fails to
                locate the library.
            OSError: raises if the ctypes.CDLL loader cannot load the library.
        """
        # Create a Lock that will used to prevent simultaneous commands from multiple
        # cameras. Main reason for this is preventing overlapping readouts.
        self._command_lock = threading.Lock()
        self._retries = retries
        super().__init__(name='sbigudrv', library_path=library_path, **kwargs)

    # Properties

    @property
    def retries(self):
        return self._retries

    @retries.setter
    def retries(self, retries):
        retries = int(retries)
        if retries < 1:
            raise ValueError("retries should be 1 or greater, got {}!".format(retries))
        self._retries = retries

    # Methods

    def get_SDK_version(self, request_type='DRIVER_STD'):
        driver_info_params = GetDriverInfoParams(driver_request_codes[request_type])
        driver_info_results = GetDriverInfoResults0()
        self.open_driver()  # Make sure driver is open
        with self._command_lock:
            self._send_command('CC_GET_DRIVER_INFO', driver_info_params, driver_info_results)
        version_string = "{}, {}".format(driver_info_results.name.decode('ascii'),
                                         self._bcd_to_string(driver_info_results.version))
        return version_string

    def get_devices(self):
        """Gets currently connected camera inf.

        Returns:
            dict: All currently connected camera serial numbers with corresponding handles.
        """
        camera_info = QueryUSBResults2()
        with self._command_lock:
            self._send_command('CC_QUERY_USB2', results=camera_info)
        if not camera_info.camerasFound:
            raise error.PanError("No SBIG camera devices found.")

        cameras = {}
        for i in range(camera_info.camerasFound):
            serial_number = camera_info.usbInfo[i].serialNumber.decode('ascii')
            device_type = "DEV_USB{}".format(i + 1)
            cameras[serial_number] = device_type

        return cameras

    def open_driver(self):
        with self._command_lock:
            self._send_command('CC_OPEN_DRIVER')

    def open_device(self, device_type):
        odp = OpenDeviceParams(device_type_codes[device_type], 0, 0)
        with self._command_lock:
            self._send_command('CC_OPEN_DEVICE', params=odp)

    def establish_link(self):
        elp = EstablishLinkParams()
        elr = EstablishLinkResults()
        with self._command_lock:
            self._send_command('CC_ESTABLISH_LINK', params=elp, results=elr)

    def get_link_status(self):
        lsr = GetLinkStatusResults()
        with self._command_lock:
            self._send_command('CC_GET_LINK_STATUS', results=lsr)
        link_status = {'established': bool(lsr.linkEstablished),
                       'base_address': int(lsr.baseAddress),
                       'camera_type': camera_types[lsr.cameraType],
                       'com_total': int(lsr.comTotal),
                       'com_failed': int(lsr.comFailed)}
        return link_status

    def get_driver_handle(self):
        ghr = GetDriverHandleResults()
        with self._command_lock:
            self._send_command('CC_GET_DRIVER_HANDLE', results=ghr)
        return ghr.handle

    def set_handle(self, handle):
        set_handle_params = SetDriverHandleParams(handle)
        self._send_command('CC_SET_DRIVER_HANDLE', params=set_handle_params)

    def get_ccd_info(self, handle):
        """
        Use Get CCD Info to gather all relevant info about CCD capabilities. Already
        have camera type, 'name' and serial number, this gets the rest.
        """
        # 'CCD_INFO_IMAGING' will get firmware version, and a list of readout modes (binning)
        # with corresponding image widths, heights, gains and also physical pixel width, height.
        ccd_info_params0 = GetCCDInfoParams(ccd_info_request_codes['CCD_INFO_IMAGING'])
        ccd_info_results0 = GetCCDInfoResults0()

        # 'CCD_INFO_EXTENDED' will get bad column info, and whether the CCD has ABG or not.
        ccd_info_params2 = GetCCDInfoParams(ccd_info_request_codes['CCD_INFO_EXTENDED'])
        ccd_info_results2 = GetCCDInfoResults2()

        # 'CCD_INFO_EXTENDED2_IMAGING' will get info like full frame/frame transfer, interline or
        # not, presence of internal frame buffer, etc.
        ccd_info_params4 = GetCCDInfoParams(ccd_info_request_codes['CCD_INFO_EXTENDED2_IMAGING'])
        ccd_info_results4 = GetCCDInfoResults4()

        # 'CCD_INFO_EXTENDED3' will get info like mechanical shutter or not, mono/colour,
        # Bayer/Truesense.
        ccd_info_params6 = GetCCDInfoParams(ccd_info_request_codes['CCD_INFO_EXTENDED3'])
        ccd_info_results6 = GetCCDInfoResults6()

        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_GET_CCD_INFO',
                               params=ccd_info_params0,
                               results=ccd_info_results0)
            self._send_command('CC_GET_CCD_INFO',
                               params=ccd_info_params2,
                               results=ccd_info_results2)
            self._send_command('CC_GET_CCD_INFO',
                               params=ccd_info_params4,
                               results=ccd_info_results4)
            self._send_command('CC_GET_CCD_INFO',
                               params=ccd_info_params6,
                               results=ccd_info_results6)

        # Now to convert all this ctypes stuff into Pythonic data structures.
        ccd_info = {'firmware version': self._bcd_to_string(ccd_info_results0.firmwareVersion),
                    'camera type': camera_types[ccd_info_results0.cameraType],
                    'camera name': str(ccd_info_results0.name, encoding='ascii'),
                    'bad columns': ccd_info_results2.columns[0:ccd_info_results2.badColumns],
                    'imaging ABG': bool(ccd_info_results2.imagingABG),
                    'serial number': str(ccd_info_results2.serialNumber, encoding='ascii'),
                    'frame transfer': bool(ccd_info_results4.capabilities_b0),
                    'electronic shutter': bool(ccd_info_results4.capabilities_b1),
                    'remote guide head support': bool(ccd_info_results4.capabilities_b2),
                    'Biorad TDI support': bool(ccd_info_results4.capabilities_b3),
                    'AO8': bool(ccd_info_results4.capabilities_b4),
                    'frame buffer': bool(ccd_info_results4.capabilities_b5),
                    'dump extra': ccd_info_results4.dumpExtra,
                    'STXL': bool(ccd_info_results6.camera_b0),
                    'mechanical shutter': not bool(ccd_info_results6.camera_b1),
                    'colour': bool(ccd_info_results6.ccd_b0),
                    'Truesense': bool(ccd_info_results6.ccd_b1)}

        readout_mode_info = self._parse_readout_info(
            ccd_info_results0.readoutInfo[0:ccd_info_results0.readoutModes])
        ccd_info['readout modes'] = readout_mode_info

        return ccd_info

    def disable_vdd_optimized(self, handle):
        """
        Stops selective lowering of the CCD's Vdd voltage to ensure consistent bias structures.

        There are many driver control parameters, almost all of which we would not want to change
        from their default values. The one exception is DCP_VDD_OPTIMIZED. From the SBIG manual:

        The DCP_VDD_OPTIMIZED parameter defaults to TRUE which lowers the CCD’s Vdd (which reduces
        amplifier glow) only for images 3 seconds and longer. This was done to increase the image
        throughput for short exposures as raising and lowering Vdd takes 100s of milliseconds. The
        lowering and subsequent raising of Vdd delays the image readout slightly which causes short
        exposures to have a different bias structure than long exposures. Setting this parameter to
        FALSE stops the short exposure optimization from occurring.

        The default behaviour will improve image throughput for exposure times of 3 seconds or less
        but at the penalty of altering the bias structure between short and long exposures. This
        could cause systematic errors in bias frames, dark current measurements, etc. It's probably
        not worth it.
        """
        set_driver_control_params = SetDriverControlParams(
            driver_control_codes['DCP_VDD_OPTIMIZED'], 0)
        self.logger.debug('Disabling DCP_VDD_OPTIMIZE on {}'.format(handle))
        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_SET_DRIVER_CONTROL', params=set_driver_control_params)

    def query_temp_status(self, handle):
        qtp = QueryTemperatureStatusParams(temp_status_request_codes['TEMP_STATUS_ADVANCED2'])
        qtr = QueryTemperatureStatusResults2()
        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_QUERY_TEMPERATURE_STATUS', qtp, qtr)

        temp_status = {'cooling_enabled': bool(qtr.coolingEnabled),
                       'fan_enabled': bool(qtr.fanEnabled),
                       'ccd_set_point': qtr.ccdSetpoint * u.Celsius,
                       'imaging_ccd_temperature': qtr.imagingCCDTemperature * u.Celsius,
                       'tracking_ccd_temperature': qtr.trackingCCDTemperature * u.Celsius,
                       'external_ccd_temperature': qtr.externalTrackingCCDTemperature * u.Celsius,
                       'ambient_temperature': qtr.ambientTemperature * u.Celsius,
                       'imaging_ccd_power': qtr.imagingCCDPower * u.percent,
                       'tracking_ccd_power': qtr.trackingCCDPower * u.percent,
                       'external_ccd_power': qtr.externalTrackingCCDPower * u.percent,
                       'heatsink_temperature': qtr.heatsinkTemperature * u.Celsius,
                       'fan_power': qtr.fanPower * u.percent,
                       'fan_speed': qtr.fanSpeed / u.minute,
                       'tracking_ccd_set_point': qtr.trackingCCDSetpoint * u.Celsius}

        return temp_status

    def set_temp_regulation(self, handle, target_temperature, enabled):
        target_temperature = get_quantity_value(target_temperature, unit=u.Celsius)

        if enabled:
            enable_code = temperature_regulation_codes['REGULATION_ON']
        else:
            enable_code = temperature_regulation_codes['REGULATION_OFF']

        set_temp_params = SetTemperatureRegulationParams2(enable_code, target_temperature)

        # Use temperature regulation autofreeze, if available (might marginally reduce read noise).
        autofreeze_code = temperature_regulation_codes['REGULATION_ENABLE_AUTOFREEZE']
        set_freeze_params = SetTemperatureRegulationParams2(autofreeze_code, target_temperature)

        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_SET_TEMPERATURE_REGULATION2', params=set_temp_params)
            self._send_command('CC_SET_TEMPERATURE_REGULATION2', params=set_freeze_params)

    def get_exposure_status(self, handle):
        """Returns the current exposure status of the camera, e.g. 'CS_IDLE', 'CS_INTEGRATING' """
        query_status_params = QueryCommandStatusParams(command_codes['CC_START_EXPOSURE2'])
        query_status_results = QueryCommandStatusResults()

        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_QUERY_COMMAND_STATUS',
                               params=query_status_params,
                               results=query_status_results)

        return statuses[query_status_results.status]

    def start_exposure(self,
                       handle,
                       seconds,
                       dark,
                       antiblooming,
                       readout_mode,
                       top,
                       left,
                       height,
                       width):
        # SBIG driver expects exposure time in 100ths of a second.
        centiseconds = int(get_quantity_value(seconds, unit=u.second) * 100)

        # This setting is ignored by most cameras (even if they do have ABG), only exceptions are
        # the TC211 versions of the Tracking CCD on the ST-7/8/etc. and the Imaging CCD of the
        # PixCel255
        if antiblooming:
            # Camera supports anti-blooming, use it on medium setting?
            abg_command_code = abg_state_codes['ABG_CLK_MED7']
        else:
            # Camera doesn't support anti-blooming, don't try to use it.
            abg_command_code = abg_state_codes['ABG_LOW7']

        if not dark:
            # Normal exposure, will open (and close) shutter
            shutter_command_code = shutter_command_codes['SC_OPEN_SHUTTER']
        else:
            # Dark frame, will keep shutter closed throughout
            shutter_command_code = shutter_command_codes['SC_CLOSE_SHUTTER']

        start_exposure_params = StartExposureParams2(ccd_codes['CCD_IMAGING'],
                                                     centiseconds,
                                                     abg_command_code,
                                                     shutter_command_code,
                                                     readout_mode_codes[readout_mode],
                                                     int(get_quantity_value(top, u.pixel)),
                                                     int(get_quantity_value(left, u.pixel)),
                                                     int(get_quantity_value(height, u.pixel)),
                                                     int(get_quantity_value(width, u.pixel)))
        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_START_EXPOSURE2', params=start_exposure_params)

    def readout(self,
                handle,
                readout_mode,
                top,
                left,
                height,
                width):
        # Set up all the parameter and result Structures that will be needed.
        readout_mode_code = readout_mode_codes[readout_mode]
        top = int(get_quantity_value(top, unit=u.pixel))
        left = int(get_quantity_value(left, unit=u.pixel))
        height = int(get_quantity_value(height, unit=u.pixel))
        width = int(get_quantity_value(width, unit=u.pixel))

        end_exposure_params = EndExposureParams(ccd_codes['CCD_IMAGING'])

        start_readout_params = StartReadoutParams(ccd_codes['CCD_IMAGING'],
                                                  readout_mode_code,
                                                  top, left,
                                                  height, width)

        readout_line_params = ReadoutLineParams(ccd_codes['CCD_IMAGING'],
                                                readout_mode_code,
                                                left, width)

        end_readout_params = EndReadoutParams(ccd_codes['CCD_IMAGING'])

        # Array to hold the image data
        image_data = np.zeros((height, width), dtype=np.uint16)
        rows_got = 0

        # Readout data
        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_END_EXPOSURE', params=end_exposure_params)
            self._send_command('CC_START_READOUT', params=start_readout_params)
            try:
                for i in range(height):
                    self._send_command('CC_READOUT_LINE',
                                       params=readout_line_params,
                                       results=as_ctypes(image_data[i]))
                    rows_got += 1
            except RuntimeError as err:
                message = 'expected {} rows, got {}: {}'.format(height, rows_got, err)
                raise RuntimeError(message)

            try:
                self._send_command('CC_END_READOUT', params=end_readout_params)
            except RuntimeError as err:
                message = "error ending readout: {}".format(err)
                raise RuntimeError(message)

        return image_data

    def cfw_init(self, handle, model='AUTO', timeout=10 * u.second):
        """
        Initialise colour filter wheel

        Sends the initialise command to the colour filter wheel attached to the camera
        specified with handle. This will generally not be required because all SBIG filter
        wheels initialise themselves on power up.

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            model (str, optional): Model of the filter wheel to control. Default is 'AUTO', which
                asks the driver to autodetect the model.
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should be
                a Quantity with time units. If a numeric type without units is given seconds will be
                assumed. Default is 10 seconds.

        Returns:
            dict: dictionary containing the 'model', 'position', 'status' and 'error' values
                returned by the driver.

        Raises:
            RuntimeError: raised if the driver returns an error
        """
        self.logger.debug("Initialising filter wheel on {}".format(handle))
        cfw_init = self._cfw_params(handle, model, CFWCommand.INIT)
        # The filterwheel init command does not block until complete, but this method should.
        # Need to poll.
        init_event = threading.Event()
        # Expect filter wheel to end up in position 1 after initialisation
        poll_thread = threading.Thread(target=self._cfw_poll,
                                       args=(handle, 1, model, init_event, timeout),
                                       daemon=True)
        poll_thread.start()
        init_event.wait()

        return self._cfw_parse_results(cfw_init)

    def cfw_query(self, handle, model='AUTO'):
        """
        Query status of the colour filter wheel

        This is mostly used to poll the filter wheel status after asking the filter wheel to move
        in order to find out when the move has completed.

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            model (str, optional): Model of the filter wheel to control. Default is 'AUTO', which
                asks the driver to autodetect the model.

        Returns:
            dict: dictionary containing the 'model', 'position', 'status' and 'error' values
                returned by the driver.

        Raises:
            RuntimeError: raised if the driver returns an error
        """
        cfw_query = self._cfw_command(handle, model, CFWCommand.QUERY)
        return self._cfw_parse_results(cfw_query)

    def cfw_get_info(self, handle, model='AUTO'):
        """
        Get info from the colour filter wheel

        This will return the usual status information plus the firmware version and the number
        of filter wheel positions.

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            model (str, optional): Model of the filter wheel to control. Default is 'AUTO', which
                asks the driver to autodetect the model.

        Returns:
            dict: dictionary containing the 'model',  'firmware_version' and 'n_positions' for the
                filter wheel.

        Raises:
            RuntimeError: raised if the driver returns an error
        """
        cfw_info = self._cfw_command(handle,
                                     model,
                                     CFWCommand.GET_INFO,
                                     CFWGetInfoSelect.FIRMWARE_VERSION)
        results = {'model': CFWModelSelect(cfw_info.cfwModel).name,
                   'firmware_version': int(cfw_info.cfwResults1),
                   'n_positions': int(cfw_info.cfwResults2)}
        msg = "Filter wheel on {}, model: {}, firmware version: {}, number of positions: {}".format(
            handle,
            results['model'],
            results['firmware_version'],
            results['n_positions'])
        self.logger.debug(msg)

        return results

    def cfw_goto(self, handle, position, model='AUTO', cfw_event=None, timeout=10 * u.second):
        """
        Move colour filer wheel to a given position

        This function returns immediately after starting the move but spawns a thread to poll the
        filter wheel until the move completes (see _cfw_poll method for details). This thread will
        log the result of the move, and optionally set a threading.Event to signal that it has
        completed.

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            position (int): position to move the filter wheel. Must an integer >= 1.
            model (str, optional): Model of the filter wheel to control. Default is 'AUTO', which
                asks the driver to autodetect the model.
            cfw_event (threading.Event, optional): Event to set once the move is complete
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should be
                a Quantity with time units. If a numeric type without units is given seconds will be
                assumed. Default is 10 seconds.

        Returns:
            dict: dictionary containing the 'model', 'position', 'status' and 'error' values
                returned by the driver.

        Raises:
            RuntimeError: raised if the driver returns an error
        """
        self.logger.debug("Moving filter wheel on {} to position {}".format(handle, position))
        # First check that the filter wheel isn't currently moving, and that the requested
        # position is valid.
        info = self.cfw_get_info(handle, model)
        if position < 1 or position > info['n_positions']:
            msg = "Position must be between 1 and {}, got {}".format(
                info['n_positions'], position)
            self.logger.error(msg)
            raise RuntimeError(msg)
        query = self.cfw_query(handle, model)
        if query['status'] == CFWStatus.BUSY:
            msg = "Attempt to move filter wheel when already moving"
            self.logger.error(msg)
            raise RuntimeError(msg)

        cfw_goto_results = self._cfw_command(handle, model, CFWCommand.GOTO, position)

        # Poll filter wheel in order to set cfw_event once move is complete
        poll_thread = threading.Thread(target=self._cfw_poll,
                                       args=(handle, position, model, cfw_event, timeout),
                                       daemon=True)
        poll_thread.start()

        return self._cfw_parse_results(cfw_goto_results)

# Private methods

    def _cfw_poll(self, handle, position, model='AUTO', cfw_event=None, timeout=None):
        """
        Polls filter wheel until the current move is complete.

        Also monitors for errors while polling and checks status and position after the move is
        complete. Optionally sets a threading.Event to signal the end of the move. Has an optional
        timeout to raise an TimeoutError is the move takes longer than expected.

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            position (int): position to move the filter wheel. Must be an integer >= 1.
            model (str, optional): Model of the filter wheel to control. Default is 'AUTO', which
                asks the driver to autodetect the model.
            cfw_event (threading.Event, optional): Event to set once the move is complete
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should be
                a Quantity with time units. If a numeric type without units is given seconds will be
                assumed.

        Raises:
            RuntimeError: raised if the driver returns an error or if the final status and position
                are not as expected.
            panoptes.utils.error.Timeout: raised if the move does not end within the period of time
                specified by the timeout argument.
        """
        if timeout is not None:
            timer = CountdownTimer(duration=timeout)

        try:
            query = self.cfw_query(handle, model)
            while query['status'] == 'BUSY':
                if timeout is not None and timer.expired():
                    msg = "Timeout waiting for filter wheel {} to move to {}".format(
                        handle, position)
                    raise error.Timeout(msg)
                time.sleep(0.1)
                query = self.cfw_query(handle, model)
        except RuntimeError as err:
            # Error returned by driver at some point while polling
            self.logger.error('Error while moving filter wheel on {} to {}: {}'.format(
                handle, position, err))
            raise err
        else:
            # No driver errors, but still check status and position
            if query['status'] == 'IDLE' and query['position'] == position:
                self.logger.debug('Filter wheel on {} moved to position {}'.format(
                    handle, query['position']))
            else:
                msg = 'Problem moving filter wheel on {} to {} - status: {}, position: {}'.format(
                    handle,
                    position,
                    query['status'],
                    query['position'])
                self.logger.error(msg)
                raise RuntimeError(msg)
        finally:
            # Regardless must always set the Event when the move has stopped.
            if cfw_event is not None:
                cfw_event.set()

    def _cfw_parse_results(self, cfw_results):
        """
        Converts filter wheel results Structure into something more Pythonic
        """
        results = {'model': CFWModelSelect(cfw_results.cfwModel).name,
                   'position': int(cfw_results.cfwPosition),
                   'status': CFWStatus(cfw_results.cfwStatus).name,
                   'error': CFWError(cfw_results.cfwError).name}

        if results['position'] == 0:
            results['position'] = float('nan')  # 0 means position unknown

        return results

    def _cfw_command(self, handle, model, *args):
        """
        Helper function to send filter wheel commands

        Args:
            handle (int): handle of the camera that the filter wheel is connected to.
            model (str): Model of the filter wheel to control.
            *args: remaining parameters for the filter wheel command
        Returns:
            CFWResults: ctypes Structure containing results of the command
        """
        cfw_params = CFWParams(CFWModelSelect[model], *args)
        cfw_results = CFWResults()
        with self._command_lock:
            self.set_handle(handle)
            self._send_command('CC_CFW', cfw_params, cfw_results)
        return cfw_results

    def _bcd_to_int(self, bcd, int_type='ushort'):
        """
        Function to decode the Binary Coded Decimals returned by the Get CCD Info command.
        These will be integers of C types ushort or ulong, encoding decimal numbers of the form
        XX.XX or XXXXXX.XX, i.e. when converting to a numerical value they will need dividing by
        100.
        """
        # BCD has been automatically converted by ctypes to a Python int. Need to convert to
        # bytes sequence of correct length and byte order. SBIG library seems to use
        # big endian byte order for the BCDs regardless of platform.
        if int_type == 'ushort':
            bcd = bcd.to_bytes(ctypes.sizeof(ctypes.c_ushort), byteorder='big')
        elif int_type == 'ulong':
            bcd = bcd.to_bytes(ctypes.sizeof(ctypes.c_ulong), byteorder='big')
        else:
            self.logger.error('Unknown integer type {}!'.format(int_type))
            return

        # Convert bytes sequence to hexadecimal string representation, which will also be the
        # string representation of the decoded binary coded decimal, apart from possible
        # leading zeros. Convert back to an int to strip the leading zeros.
        return int(bcd.hex())

    def _bcd_to_float(self, bcd, int_type='ushort'):
        # Includes conversion to intended numerical value, i.e. division by 100
        return self._bcd_to_int(bcd, int_type) / 100.0

    def _bcd_to_string(self, bcd, int_type='ushort'):
        # Includes conversion to intended numerical value, i.e. division by 100
        s = str(self._bcd_to_int(bcd, int_type))
        return "{}.{}".format(s[:-2], s[-2:])

    def _parse_readout_info(self, infos):
        readout_mode_info = {}

        for info in infos:
            mode = readout_modes[info.mode]
            gain = self._bcd_to_float(info.gain)
            pixel_width = self._bcd_to_float(info.pixelWidth, int_type='ulong')
            pixel_height = self._bcd_to_float(info.pixelHeight, int_type='ulong')
            readout_mode_info[mode] = {'width': info.width * u.pixel,
                                       'height': info.height * u.pixel,
                                       'gain': gain * u.electron / u.adu,
                                       'pixel width': pixel_width * u.um,
                                       'pixel height': pixel_height * u.um}

        return readout_mode_info

    def _send_command(self, command, params=None, results=None):
        """
        Function for sending a command to the SBIG Universal Driver/Library.

        Args:
            command (string): Name of command to send
            params (ctypes.Structure, optional): Subclass of Structure
                                                 containing command parameters
            results (ctypes.Structure, optional): Subclass of Structure to
                                                  store command results

        Returns:
            error (str): error message received from the SBIG driver, will be
                'CE_NO_ERROR' if no error occurs.

        Raises:
            KeyError: Raised if command not in SBIG command list
            RuntimeError: Raised if return code indicates a fatal error, or is
                not recognised
        """
        # Look up integer command code for the given command string, raises
        # KeyError if no matches found.
        try:
            command_code = command_codes[command]
        except KeyError:
            msg = "Invalid SBIG command '{}'!".format(command)
            self.logger.error(msg)
            raise KeyError(msg)

        error = None
        retries_remaining = self.retries

        while error != 'CE_NO_ERROR' and retries_remaining > 0:

            # Send the command to the driver. Need to pass pointers to params,
            # results structs or None (which gets converted to a null pointer).
            return_code = self._CDLL.SBIGUnivDrvCommand(
                command_code,
                (ctypes.byref(params) if params else None),
                (ctypes.byref(results) if results else None))

            # Look up the error message for the return code, raises Error if no
            # match found. This should never happen, and if it does it probably
            # indicates a serious problem such an outdated driver that is
            # incompatible with the camera in use.
            try:
                error = errors[return_code]
            except KeyError:
                msg = "SBIG Driver returned unknown error code '{}'".format(return_code)
                self.logger.error(msg)
                raise RuntimeError(msg)

            retries_remaining -= 1

        # Raise a RuntimeError exception if return code is not 0 (no error).
        # This is probably excessively cautious and will need to be relaxed,
        # there are likely to be situations where other return codes don't
        # necessarily indicate a fatal error.
        # Will not raise a RunTimeError if the error is 'CE_DRIVER_NOT_CLOSED'
        # because this only indicates an attempt to open the driver then it is
        # already open.
        if error not in ('CE_NO_ERROR', 'CE_DRIVER_NOT_CLOSED'):
            if error == 'CE_CFW_ERROR':
                cfw_error_code = results.cfwError
                try:
                    error = "CFW {}".format(CFWError(cfw_error_code).name)
                except ValueError:
                    msg = "SBIG Driver return unknown CFW error code '{}'".format(cfw_error_code)
                    self.logger.error(msg)
                    raise RuntimeError(msg)

            msg = "SBIG Driver returned error '{}'!".format(error)
            self.logger.error(msg)
            raise RuntimeError(msg)

        return error


#################################################################################
# Commands and error messages
#################################################################################


# Camera command codes. Doesn't include the 'SBIG only" commands.
command_codes = {'CC_NULL': 0,
                 'CC_START_EXPOSURE': 1,
                 'CC_END_EXPOSURE': 2,
                 'CC_READOUT_LINE': 3,
                 'CC_DUMP_LINES': 4,
                 'CC_SET_TEMPERATURE_REGULATION': 5,
                 'CC_QUERY_TEMPERATURE_STATUS': 6,
                 'CC_ACTIVATE_RELAY': 7,
                 'CC_PULSE_OUT': 8,
                 'CC_ESTABLISH_LINK': 9,
                 'CC_GET_DRIVER_INFO': 10,
                 'CC_GET_CCD_INFO': 11,
                 'CC_QUERY_COMMAND_STATUS': 12,
                 'CC_MISCELLANEOUS_CONTROL': 13,
                 'CC_READ_SUBTRACT_LINE': 14,
                 'CC_UPDATE_CLOCK': 15,
                 'CC_READ_OFFSET': 16,
                 'CC_OPEN_DRIVER': 17,
                 'CC_CLOSE_DRIVER': 18,
                 'CC_TX_SERIAL_BYTES': 19,
                 'CC_GET_SERIAL_STATUS': 20,
                 'CC_AO_TIP_TILT': 21,
                 'CC_AO_SET_FOCUS': 22,
                 'CC_AO_DELAY': 23,
                 'CC_GET_TURBO_STATUS': 24,
                 'CC_END_READOUT': 25,
                 'CC_GET_US_TIMER': 26,
                 'CC_OPEN_DEVICE': 27,
                 'CC_CLOSE_DEVICE': 28,
                 'CC_SET_IRQL': 29,
                 'CC_GET_IRQL': 30,
                 'CC_GET_LINE': 31,
                 'CC_GET_LINK_STATUS': 32,
                 'CC_GET_DRIVER_HANDLE': 33,
                 'CC_SET_DRIVER_HANDLE': 34,
                 'CC_START_READOUT': 35,
                 'CC_GET_ERROR_STRING': 36,
                 'CC_SET_DRIVER_CONTROL': 37,
                 'CC_GET_DRIVER_CONTROL': 38,
                 'CC_USB_AD_CONTROL': 39,
                 'CC_QUERY_USB': 40,
                 'CC_GET_PENTIUM_CYCLE_COUNT': 41,
                 'CC_RW_USB_I2C': 42,
                 'CC_CFW': 43,
                 'CC_BIT_IO': 44,
                 'CC_USER_EEPROM': 45,
                 'CC_AO_CENTER': 46,
                 'CC_BTDI_SETUP': 47,
                 'CC_MOTOR_FOCUS': 48,
                 'CC_QUERY_ETHERNET': 49,
                 'CC_START_EXPOSURE2': 50,
                 'CC_SET_TEMPERATURE_REGULATION2': 51,
                 'CC_READ_OFFSET2': 52,
                 'CC_DIFF_GUIDER': 53,
                 'CC_COLUMN_EEPROM': 54,
                 'CC_CUSTOMER_OPTIONS': 55,
                 'CC_DEBUG_LOG': 56,
                 'CC_QUERY_USB2': 57,
                 'CC_QUERY_ETHERNET2': 58,
                 'CC_GET_AO_MODEL': 59,
                 'CC_QUERY_USB3': 60,
                 'CC_QUERY_COMMAND_STATUS2': 61}

# Reversed dictionary, just in case you ever need to look up a command given a
# command code.
commands = {code: command for command, code in command_codes.items()}


# Camera error messages
errors = {0: 'CE_NO_ERROR',
          1: 'CE_CAMERA_NOT_FOUND',
          2: 'CE_EXPOSURE_IN_PROGRESS',
          3: 'CE_NO_EXPOSURE_IN_PROGRESS',
          4: 'CE_UNKNOWN_COMMAND',
          5: 'CE_BAD_CAMERA_COMMAND',
          6: 'CE_BAD_PARAMETER',
          7: 'CE_TX_TIMEOUT',
          8: 'CE_RX_TIMEOUT',
          9: 'CE_NAK_RECEIVED',
          10: 'CE_CAN_RECEIVED',
          11: 'CE_UNKNOWN_RESPONSE',
          12: 'CE_BAD_LENGTH',
          13: 'CE_AD_TIMEOUT',
          14: 'CE_KBD_ESC',
          15: 'CE_CHECKSUM_ERROR',
          16: 'CE_EEPROM_ERROR',
          17: 'CE_SHUTTER_ERROR',
          18: 'CE_UNKNOWN_CAMERA',
          19: 'CE_DRIVER_NOT_FOUND',
          20: 'CE_DRIVER_NOT_OPEN',
          21: 'CE_DRIVER_NOT_CLOSED',
          22: 'CE_SHARE_ERROR',
          23: 'CE_TCE_NOT_FOUND',
          24: 'CE_AO_ERROR',
          25: 'CE_ECP_ERROR',
          26: 'CE_MEMORY_ERROR',
          27: 'CE_DEVICE_NOT_FOUND',
          28: 'CE_DEVICE_NOT_OPEN',
          29: 'CE_DEVICE_NOT_CLOSED',
          30: 'CE_DEVICE_NOT_IMPLEMENTED',
          31: 'CE_DEVICE_DISABLED',
          32: 'CE_OS_ERROR',
          33: 'CE_SOCK_ERROR',
          34: 'CE_SERVER_NOT_FOUND',
          35: 'CE_CFW_ERROR',
          36: 'CE_MF_ERROR',
          37: 'CE_FIRMWARE_ERROR',
          38: 'CE_DIFF_GUIDER_ERROR',
          39: 'CE_RIPPLE_CORRECTION_ERROR',
          40: 'CE_EZUSB_RESET',
          41: 'CE_INCOMPATIBLE_FIRMWARE',
          42: 'CE_INVALID_HANDLE',
          43: 'CE_NEXT_ERROR'}

# Reverse dictionary, just in case you ever need to look up an error code given
# an error name
error_codes = {error: error_code for error_code, error in errors.items()}


#################################################################################
# Query USB Info related.
#################################################################################


class QueryUSBInfo(ctypes.Structure):
    """
    ctypes (Sub-)Structure used to hold details of individual cameras returned
    by 'CC_QUERY_USB' command
    """
    # Rather than use C99 _Bool type SBIG library uses 0 = False, 1 = True
    _fields_ = [('cameraFound', ctypes.c_ushort),
                ('cameraType', ctypes.c_ushort),
                ('name', ctypes.c_char * 64),
                ('serialNumber', ctypes.c_char * 10)]


class QueryUSBResults(ctypes.Structure):
    """
    ctypes Structure used to hold the results from 'CC_QUERY_USB' command (max 4 cameras).
    """
    _fields_ = [('camerasFound', ctypes.c_ushort),
                ('usbInfo', QueryUSBInfo * 4)]


class QueryUSBResults2(ctypes.Structure):
    """
    ctypes Structure used to hold the results from 'CC_QUERY_USB2' command (max 8 cameras).
    """
    _fields_ = [('camerasFound', ctypes.c_ushort),
                ('usbInfo', QueryUSBInfo * 8)]


class QueryUSBResults3(ctypes.Structure):
    """
    ctypes Structure used to hold the results from 'CC_QUERY_USB3' command (max 24 cameras).
    """
    _fields_ = [('camerasFound', ctypes.c_ushort),
                ('usbInfo', QueryUSBInfo * 24)]


# Camera type codes, returned by Query USB Info, Establish Link, Get CCD Info, etc.
camera_types = {4: "ST7_CAMERA",
                5: "ST8_CAMERA",
                6: "ST5C_CAMERA",
                7: "TCE_CONTROLLER",
                8: "ST237_CAMERA",
                9: "STK_CAMERA",
                10: "ST9_CAMERA",
                11: "STV_CAMERA",
                12: "ST10_CAMERA",
                13: "ST1K_CAMERA",
                14: "ST2K_CAMERA",
                15: "STL_CAMERA",
                16: "ST402_CAMERA",
                17: "STX_CAMERA",
                18: "ST4K_CAMERA",
                19: "STT_CAMERA",
                20: "STI_CAMERA",
                21: "STF_CAMERA",
                22: "NEXT_CAMERA",
                0xFFFF: "NO_CAMERA"}

# Reverse dictionary
camera_type_codes = {camera: code for code, camera in camera_types.items()}


#################################################################################
# Open Device, Establish Link, Get Link status related
#################################################################################


# Device types by code. Used with Open Device, etc.
device_types = {0: "DEV_NONE",
                1: "DEV_LPT1",
                2: "DEV_LPT2",
                3: "DEV_LPT3",
                0x7F00: "DEV_USB",
                0x7F01: "DEV_ETH",
                0x7F02: "DEV_USB1",
                0x7F03: "DEV_USB2",
                0x7F04: "DEV_USB3",
                0x7F05: "DEV_USB4",
                0x7F06: "DEV_USB5",
                0x7F07: "DEV_USB6",
                0x7F08: "DEV_USB7",
                0x7F09: "DEV_USB8",
                0x7F0A: "DEV_USB9",
                0x7F0B: "DEV_USB10",
                0x7F0C: "DEV_USB11",
                0x7F0D: "DEV_USB12",
                0x7F0E: "DEV_USB13",
                0x7F0F: "DEV_USB14",
                0x7F10: "DEV_USB15",
                0x7F11: "DEV_USB16",
                0x7F12: "DEV_USB17",
                0x7F13: "DEV_USB18",
                0x7F14: "DEV_USB19",
                0x7F15: "DEV_USB20",
                0x7F16: "DEV_USB21",
                0x7F17: "DEV_USB22",
                0x7F18: "DEV_USB23",
                0x7F19: "DEV_USB24"}

# Reverse dictionary
device_type_codes = {device: code for code, device in device_types.items()}


class OpenDeviceParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Open Device command.
    """
    _fields_ = [('deviceType', ctypes.c_ushort),
                ('lptBaseAddress', ctypes.c_ushort),
                ('ipAddress', ctypes.c_ulong)]


class EstablishLinkParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Establish Link command.
    """
    _fields_ = [('sbigUseOnly', ctypes.c_ushort)]


class EstablishLinkResults(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Establish Link command.
    """
    _fields_ = [('cameraType', ctypes.c_ushort)]


class GetLinkStatusResults(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get Link Status command.
    """
    _fields_ = [('linkEstablished', ctypes.c_ushort),
                ('baseAddress', ctypes.c_ushort),
                ('cameraType', ctypes.c_ushort),
                ('comTotal', ctypes.c_ulong),
                ('comFailed', ctypes.c_ulong)]


#################################################################################
# Get Driver Handle, Set Driver Handle related
#################################################################################


class GetDriverHandleResults(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get Driver Handle command.
    The handle is the camera ID used when switching control between connected
    cameras with the Set Driver Handle command.
    """
    _fields_ = [('handle', ctypes.c_short)]


# Used to disconnect from a camera in order to get the handle for another
# Had to google to find this value, it is NOT in sbigudrv.h or the
# SBIG Universal Driver docs.
INVALID_HANDLE_VALUE = -1


class SetDriverHandleParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameter for the Set Driver Handle command.
    """
    _fields_ = [('handle', ctypes.c_short)]


#################################################################################
# Temperature and cooling control related
#################################################################################


class QueryTemperatureStatusParams(ctypes.Structure):
    """
    ctypes Structure used to hold the parameters for the
    Query Temperature Status command.
    """
    _fields_ = [('request', ctypes.c_ushort)]


temp_status_requests = {0: 'TEMP_STATUS_STANDARD',
                        1: 'TEMP_STATUS_ADVANCED',
                        2: 'TEMP_STATUS_ADVANCED2'}

temp_status_request_codes = {request: code for code, request in temp_status_requests.items()}


class QueryTemperatureStatusResults(ctypes.Structure):
    """
    ctypes Structure used to hold the results from the Query Temperature Status
    command (standard version).
    """
    _fields_ = [('enabled', ctypes.c_ushort),
                ('ccdSetpoint', ctypes.c_ushort),
                ('power', ctypes.c_ushort),
                ('ccdThermistor', ctypes.c_ushort),
                ('ambientThermistor', ctypes.c_ushort)]


class QueryTemperatureStatusResults2(ctypes.Structure):
    """
    ctypes Structure used to hold the results from the Query Temperature Status
    command (extended version).
    """
    _fields_ = [('coolingEnabled', ctypes.c_ushort),
                ('fanEnabled', ctypes.c_ushort),
                ('ccdSetpoint', ctypes.c_double),
                ('imagingCCDTemperature', ctypes.c_double),
                ('trackingCCDTemperature', ctypes.c_double),
                ('externalTrackingCCDTemperature', ctypes.c_double),
                ('ambientTemperature', ctypes.c_double),
                ('imagingCCDPower', ctypes.c_double),
                ('trackingCCDPower', ctypes.c_double),
                ('externalTrackingCCDPower', ctypes.c_double),
                ('heatsinkTemperature', ctypes.c_double),
                ('fanPower', ctypes.c_double),
                ('fanSpeed', ctypes.c_double),
                ('trackingCCDSetpoint', ctypes.c_double)]


temperature_regulations = {0: "REGULATION_OFF",
                           1: "REGULATION_ON",
                           2: "REGULATION_OVERRIDE",
                           3: "REGULATION_FREEZE",
                           4: "REGULATION_UNFREEZE",
                           5: "REGULATION_ENABLE_AUTOFREEZE",
                           6: "REGULATION_DISABLE_AUTOFREEZE"}

temperature_regulation_codes = {regulation: code for code, regulation in
                                temperature_regulations.items()}


class SetTemperatureRegulationParams(ctypes.Structure):
    """
    ctypes Structure used to hold the parameters for the
    Set Temperature Regulation command.
    """
    _fields_ = [('regulation', ctypes.c_ushort),
                ('ccdSetpoint', ctypes.c_ushort)]


class SetTemperatureRegulationParams2(ctypes.Structure):
    """
    ctypes Structure used to hold the parameters for the
    Set Temperature Regulation 2 command.
    """
    _fields_ = [('regulation', ctypes.c_ushort),
                ('ccdSetpoint', ctypes.c_double)]


################################################################################
# Get CCD Info related
################################################################################


class GetCCDInfoParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Get CCD Info command,
    used obtain the details & capabilities of the connected camera.
    """
    _fields_ = [('request', ctypes.c_ushort)]


ccd_info_requests = {0: 'CCD_INFO_IMAGING',
                     1: 'CCD_INFO_TRACKING',
                     2: 'CCD_INFO_EXTENDED',
                     3: 'CCD_INFO_EXTENDED_5C',
                     4: 'CCD_INFO_EXTENDED2_IMAGING',
                     5: 'CCD_INFO_EXTENDED2_TRACKING',
                     6: 'CCD_INFO_EXTENDED3'}

ccd_info_request_codes = {request: code for code, request in ccd_info_requests.items()}


class ReadoutInfo(ctypes.Structure):
    """
    ctypes Structure to store details of an individual readout mode. An array of up
    to 20 of these will be returned as part of the GetCCDInfoResults0 struct when the
    Get CCD Info command is used with request 'CCD_INFO_IMAGING'.

    The gain field is a 4 digit Binary Coded Decimal (yes, really) of the form XX.XX,
    in units of electrons/ADU.

    The pixel_width and pixel_height fields are 6 digit Binary Coded Decimals for the
    form XXXXXX.XX in units of microns, helpfully supporting pixels up to 1 metre across.
    """
    _fields_ = [('mode', ctypes.c_ushort),
                ('width', ctypes.c_ushort),
                ('height', ctypes.c_ushort),
                ('gain', ctypes.c_ushort),
                ('pixelWidth', ctypes.c_ulong),
                ('pixelHeight', ctypes.c_ulong)]


class GetCCDInfoResults0(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get CCD Info command when used with
    requests 'CCD_INFO_IMAGING' or 'CCD_INFO_TRACKING'.

    The firmwareVersion field is 4 digit binary coded decimal of the form XX.XX.
    """
    _fields_ = [('firmwareVersion', ctypes.c_ushort),
                ('cameraType', ctypes.c_ushort),
                ('name', ctypes.c_char * 64),
                ('readoutModes', ctypes.c_ushort),
                ('readoutInfo', ReadoutInfo * 20)]


class GetCCDInfoResults2(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get CCD Info command when used with
    request 'CCD_INFO_EXTENDED'.
    """
    _fields_ = [('badColumns', ctypes.c_ushort),
                ('columns', ctypes.c_ushort * 4),
                ('imagingABG', ctypes.c_ushort),
                ('serialNumber', ctypes.c_char * 10)]


class GetCCDInfoResults4(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get CCD Info command when used with
    requests 'CCD_INFO_EXTENDED2_IMAGING' or 'CCD_INFO_EXTENDED2_TRACKING'.

    The capabilitiesBits is a bitmap, yay.
    """
    _fields_ = [('capabilities_b0', ctypes.c_int, 1),
                ('capabilities_b1', ctypes.c_int, 1),
                ('capabilities_b2', ctypes.c_int, 1),
                ('capabilities_b3', ctypes.c_int, 1),
                ('capabilities_b4', ctypes.c_int, 1),
                ('capabilities_b5', ctypes.c_int, 1),
                ('capabilities_unusued', ctypes.c_int, ctypes.sizeof(ctypes.c_ushort) * 8 - 6),
                ('dumpExtra', ctypes.c_ushort)]


class GetCCDInfoResults6(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Get CCD Info command when used with
    the request 'CCD_INFO_EXTENDED3'.

    The sbigudrv.h C header says there should be three bitmask fields, each of type
    ulong, which would be 64 bits on this platform (OS X), BUT trial and error has
    determined they're actually 32 bits long.
    """
    _fields_ = [('camera_b0', ctypes.c_int, 1),
                ('camera_b1', ctypes.c_int, 1),
                ('camera_unused', ctypes.c_int, 30),
                ('ccd_b0', ctypes.c_int, 1),
                ('ccd_b1', ctypes.c_int, 1),
                ('ccd_unused', ctypes.c_int, 30),
                ('extraBits', ctypes.c_int, 32)]


#################################################################################
# Get Driver Control, Set Driver Control related
#################################################################################


driver_control_params = {i: param for i, param in enumerate(('DCP_USB_FIFO_ENABLE',
                                                             'DCP_CALL_JOURNAL_ENABLE',
                                                             'DCP_IVTOH_RATIO',
                                                             'DCP_USB_FIFO_SIZE',
                                                             'DCP_USB_DRIVER',
                                                             'DCP_KAI_RELGAIN',
                                                             'DCP_USB_PIXEL_DL_ENABLE',
                                                             'DCP_HIGH_THROUGHPUT',
                                                             'DCP_VDD_OPTIMIZED',
                                                             'DCP_AUTO_AD_GAIN',
                                                             'DCP_NO_HCLKS_FOR_INTEGRATION',
                                                             'DCP_TDI_MODE_ENABLE',
                                                             'DCP_VERT_FLUSH_CONTROL_ENABLE',
                                                             'DCP_ETHERNET_PIPELINE_ENABLE',
                                                             'DCP_FAST_LINK',
                                                             'DCP_OVERSCAN_ROWSCOLS',
                                                             'DCP_PIXEL_PIPELINE_ENABLE',
                                                             'DCP_COLUMN_REPAIR_ENABLE',
                                                             'DCP_WARM_PIXEL_REPAIR_ENABLE',
                                                             'DCP_WARM_PIXEL_REPAIR_COUNT',
                                                             'DCP_TDI_MODE_DRIFT_RATE',
                                                             'DCP_OVERRIDE_AD_GAIN',
                                                             'DCP_ENABLE_AUTO_OFFSET',
                                                             'DCP_LAST'))}

driver_control_codes = {param: code for code, param in driver_control_params.items()}


class GetDriverControlParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Get Driver Control command,
    used to query the value of a specific driver control parameter.
    """
    _fields_ = [('controlParameter', ctypes.c_ushort), ]


class GetDriverControlResults(ctypes.Structure):
    """
    ctypes Structure to hold the result from the Get Driver Control command,
    used to query the value of a specific driver control parameter
    """
    _fields_ = [('controlValue', ctypes.c_ulong), ]


class SetDriverControlParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Set Driver Control command,
    used to set the value of a specific driver control parameter
    """
    _fields_ = [('controlParameter', ctypes.c_ushort),
                ('controlValue', ctypes.c_ulong)]


#################################################################################
# Start Exposure, Query Command Status, End Exposure related
#################################################################################


class StartExposureParams2(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Start Exposure 2 command.
    (The Start Exposure command is deprecated.)
    """
    _fields_ = [('ccd', ctypes.c_ushort),
                ('exposureTime', ctypes.c_ulong),
                ('abgState', ctypes.c_ushort),
                ('openShutter', ctypes.c_ushort),
                ('readoutMode', ctypes.c_ushort),
                ('top', ctypes.c_ushort),
                ('left', ctypes.c_ushort),
                ('height', ctypes.c_ushort),
                ('width', ctypes.c_ushort)]


# CCD selection for cameras with built in or connected tracking CCDs
ccds = {0: 'CCD_IMAGING',
        1: 'CCD_TRACKING',
        2: 'CCD_EXT_TRACKING'}

ccd_codes = {ccd: code for code, ccd in ccds.items()}

# Anti-Blooming Gate states
abg_states = {0: 'ABG_LOW7',
              1: 'ABG_CLK_LOW7',
              2: 'ABG_CLK_MED7',
              3: 'ABG_CLK_HI7'}

abg_state_codes = {abg: code for code, abg in abg_states.items()}

# Shutter mode commands
shutter_commands = {0: 'SC_LEAVE_SHUTTER',
                    1: 'SC_OPEN_SHUTTER',
                    2: 'SC_CLOSE_SHUTTER',
                    3: 'SC_INITIALIZE_SHUTTER',
                    4: 'SC_OPEN_EXP_SHUTTER',
                    5: 'SC_CLOSE_EXT_SHUTTER'}

shutter_command_codes = {command: code for code, command in shutter_commands.items()}

# Readout binning modes
readout_modes = {0: 'RM_1X1',
                 1: 'RM_2X2',
                 2: 'RM_3X3',
                 3: 'RM_NX1',
                 4: 'RM_NX2',
                 5: 'RM_NX3',
                 6: 'RM_1X1_VOFFCHIP',
                 7: 'RM_2X2_VOFFCHIP',
                 8: 'RM_3X3_VOFFCHIP',
                 9: 'RM_9X9',
                 10: 'RM_NXN'}

readout_mode_codes = {mode: code for code, mode in readout_modes.items()}


# Command status codes and corresponding messages as returned by
# Query Command Status
statuses = {0: "CS_IDLE",
            1: "CS_IN_PROGRESS",
            2: "CS_INTEGRATING",
            3: "CS_INTEGRATION_COMPLETE"}

# Reverse dictionary
status_codes = {status: code for code, status in statuses.items()}


class QueryCommandStatusParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Query Command Status
    command.
    """
    _fields_ = [('command', ctypes.c_ushort)]


class QueryCommandStatusResults(ctypes.Structure):
    """
    ctypes Structure to hold the results from the Query Command Status command.
    """
    _fields_ = [('status', ctypes.c_ushort)]


class EndExposureParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the End Exposure command.
    """
    _fields_ = [('ccd', ctypes.c_ushort)]


#################################################################################
# Start Readout, Readout Line, End Readout related
#################################################################################


class StartReadoutParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Start Readout command.
    """
    _fields_ = [('ccd', ctypes.c_ushort),
                ('readoutMode', ctypes.c_ushort),
                ('top', ctypes.c_ushort),
                ('left', ctypes.c_ushort),
                ('height', ctypes.c_ushort),
                ('width', ctypes.c_ushort)]


class ReadoutLineParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the Readout Line command.
    """
    _fields_ = [('ccd', ctypes.c_ushort),
                ('readoutMode', ctypes.c_ushort),
                ('pixelStart', ctypes.c_ushort),
                ('pixelLength', ctypes.c_ushort)]


class EndReadoutParams(ctypes.Structure):
    """
    ctypes Structure to hold the parameters for the End Readout Params.
    """
    _fields_ = [('ccd', ctypes.c_ushort)]


#################################################################################
# Get Driver Info related
#################################################################################


# Requests relevant to Get Driver Info command
driver_requests = {0: "DRIVER_STD",
                   1: "DRIVER_EXTENDED",
                   2: "DRIVER_USB_LOADER"}

# Reverse dictionary
driver_request_codes = {request: code for code, request in driver_requests.items()}


class GetDriverInfoParams(ctypes.Structure):
    """
    ctypes Structure used to hold the parameters for the Get Driver Info command
    """
    _fields_ = [('request', ctypes.c_ushort)]


class GetDriverInfoResults0(ctypes.Structure):
    """
    ctypes Structure used to hold the results from the Get Driver Info command
    """
    _fields_ = [('version', ctypes.c_ushort),
                ('name', ctypes.c_char * 64),
                ('maxRequest', ctypes.c_ushort)]


#################################################################################
# Filter wheel related
#################################################################################

class CFWParams(ctypes.Structure):
    """
    ctypes Structure used to hold the parameters for the CFW (colour filter wheel) command
    """
    _fields_ = [('cfwModel', ctypes.c_ushort),
                ('cfwCommand', ctypes.c_ushort),
                ('cfwParam1', ctypes.c_ulong),
                ('cfwParam2', ctypes.c_ulong),
                ('outLength', ctypes.c_ushort),
                ('outPtr', ctypes.c_char_p),
                ('inLength', ctypes.c_ushort),
                ('inPtr', ctypes.c_char_p)]


class CFWResults(ctypes.Structure):
    """
    ctypes Structure used to fold the results from the CFW (colour filer wheel) command
    """
    _fields_ = [('cfwModel', ctypes.c_ushort),
                ('cfwPosition', ctypes.c_ushort),
                ('cfwStatus', ctypes.c_ushort),
                ('cfwError', ctypes.c_ushort),
                ('cfwResults1', ctypes.c_ulong),
                ('cfwResults2', ctypes.c_ulong)]


@enum.unique
class CFWModelSelect(enum.IntEnum):
    """
    Filter wheel model selection enum
    """
    UNKNOWN = 0
    CFW2 = enum.auto()
    CFW5 = enum.auto()
    CFW8 = enum.auto()
    CFWL = enum.auto()
    CFW402 = enum.auto()
    AUTO = enum.auto()
    CFW6A = enum.auto()
    CFW10 = enum.auto()
    CFW10_SERIAL = enum.auto()
    CFW9 = enum.auto()
    CFWL8 = enum.auto()
    CFWL8G = enum.auto()
    CFW1603 = enum.auto()
    FW5_STX = enum.auto()
    FW5_8300 = enum.auto()
    FW8_8300 = enum.auto()
    FW7_STX = enum.auto()
    FW8_STT = enum.auto()
    FW5_STF_DETENT = enum.auto()


@enum.unique
class CFWCommand(enum.IntEnum):
    """
    Filter wheel command enum
    """
    QUERY = 0
    GOTO = enum.auto()
    INIT = enum.auto()
    GET_INFO = enum.auto()
    OPEN_DEVICE = enum.auto()
    CLOSE_DEVICE = enum.auto()


@enum.unique
class CFWStatus(enum.IntEnum):
    """
    Filter wheel status enum
    """
    UNKNOWN = 0
    IDLE = enum.auto()
    BUSY = enum.auto()


@enum.unique
class CFWError(enum.IntEnum):
    """
    Filter wheel errors enum
    """
    NONE = 0
    BUSY = enum.auto()
    BAD_COMMAND = enum.auto()
    CAL_ERROR = enum.auto()
    MOTOR_TIMEOUT = enum.auto()
    BAD_MODEL = enum.auto()
    DEVICE_NOT_CLOSED = enum.auto()
    DEVICE_NOT_OPEN = enum.auto()
    I2C_ERROR = enum.auto()


@enum.unique
class CFWGetInfoSelect(enum.IntEnum):
    """
    Filter wheel get info select enum
    """
    FIRMWARE_VERSION = 0
    CAL_DATA = enum.auto()
    DATA_REGISTERS = enum.auto()
