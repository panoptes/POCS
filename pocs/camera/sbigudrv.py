"""
Low level interface to the SBIG Unversal Driver/Library.

Reproduces in Python (using ctypes) the C interface provided by SBIG's shared
library, i.e. 1 function that does 72 different things selected by passing an
integer as the first argument. This is basically a direct translation of the
enums and structs defined in the library C-header to Python dicts and
ctypes.Structures, plus a very simple class (SBIGDriver) to load the library
and call the single command function (SBIGDriver.send_command()).
"""
import platform
import ctypes
from os import path

from .. import PanBase
from ..utils import error

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
                 'CC_QUERY_ETHERNET2': 58}

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
          41: 'CE_NEXT_ERROR'}

# Reverse dictionary, just in case you ever need to look up an error code given
# an error name
error_codes = {error: error_code for error_code, error in errors.items()}


# Command status codes and corresponding messages as returned by
# Query Command Status
statuses = {0: "CS_IDLE",
            1: "CS_IN_PROGRESS",
            2: "CS_INTEGRATING",
            3: "CS_INTEGRATION_COMPLETE"}

# Reverse dictionary
status_codes = {status: code for code, status in statuses.items()}


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


# Camera type codes, returned by Establish Link, Get CCD Info, etc.
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


class QUERY_USB_INFO(ctypes.Structure):
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
    ctypes Structure used to hold the results from 'CC_QUERY_USB' command
    """
    _fields_ = [('camerasFound', ctypes.c_ushort),
                ('usbInfo', QUERY_USB_INFO * 4)]


class QueryUSBResults2(ctypes.Structure):
    """
    ctypes Structure used to hold the results from 'CC_QUERY_USB2' command
    """
    _fields_ = [('camerasFound', ctypes.c_ushort),
                ('usbInfo', QUERY_USB_INFO * 8)]


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

temperature_regulation_codes = {regulation: code for code, regulation in temperature_regulations.items()}


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


# Device types by code. Used with Open Device, Query USB, etc.
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
                0x7F09: "DEV_USB8"}

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


class SBIGDriver(PanBase):
    def __init__(self, library_path=False, library_name=False, *args, **kwargs):
        """
        Main class representing the SBIG Universal Driver/Library interface.
        On construction loads SBIG's shared library which must have already
        been installed (see http://archive.sbig.com/sbwhtmls/devsw.htm). The
        name and location of the shared library can be manually specified with
        the library_path and library_name arguments, otherwise will try OS
        specific defaults.

        Args:
            library_path (string, optional): shared library path,
             e.g. '/usr/local/lib/'
            library_name (string, optional): shared library name,
             e.g. 'lubsbigudrv.so'

        Returns:
            `~pocs.camera.sbig.SBIGDriver`
        """
        super().__init__(*args, **kwargs)

        # Open library
        self.logger.debug('Opening SBIGUDrv library')
        self._CDLL = ctypes.CDLL(self._get_library_path(library_path, library_name))

        # Open driver
        self.logger.debug('Opening SBIGUDrv driver')
        self.send_command('CC_OPEN_DRIVER')
        self.driver_open = True

        # Query USB bus for connected cameras
        self.logger.debug('Searching for connected SBIG cameras')
        self.camera_info = QueryUSBResults2()
        self.send_command('CC_QUERY_USB2', results=self.camera_info)
        self.logger.info('Found {} SBIG cameras'.format(self.camera_info.camerasFound))
        self.send_command('CC_CLOSE_DRIVER')

        # Connect to each camera in turn, obtain its 'handle' and store.
        self.handles = []

        for i in range(self.camera_info.camerasFound):
            self.send_command('CC_OPEN_DRIVER')
            odp = OpenDeviceParams(device_type_codes['DEV_USB{}'.format(i + 1)],
                                   0, 0)
            self.send_command('CC_OPEN_DEVICE', params=odp)

            elp = EstablishLinkParams()
            elr = EstablishLinkResults()
            self.send_command('CC_ESTABLISH_LINK', params=elp, results=elr)

            ghr = GetDriverHandleResults()
            self.send_command('CC_GET_DRIVER_HANDLE', results=ghr)
            self.handles.append(ghr.handle)

            # This seems to have the side effect of closing both device and
            # driver.
            shp = SetDriverHandleParams(INVALID_HANDLE_VALUE)
            self.send_command('CC_SET_DRIVER_HANDLE', params=shp)

        # Prepare to keep a count of how many handles have been assigned to Camera objects
        self.assigned_handles = 0

        # Reopen driver ready for next command
        self.send_command('CC_OPEN_DRIVER')

    def assign_handle(self):
        """
        Returns the next unassigned camera handle, along with basic info on the coresponding camera.
        """
        try:
            handle = self.handles[self.assigned_handles]
        except IndexError:
            # All handles already assigned, must be trying to intialising more cameras than are connected.
            self.logger.error('SBIG camera not connected!')
            return (INVALID_HANDLE_VALUE, None, None, None)

        camera_type = camera_types[self.camera_info.usbInfo[self.assigned_handles].cameraType]
        camera_name = str(self.camera_info.usbInfo[self.assigned_handles].name, encoding='ascii')
        camera_serial = str(self.camera_info.usbInfo[self.assigned_handles].serialNumber, encoding='ascii')

        self.logger.debug('Assigning handle {} to SBIG camera'.format(handle))
        self.assigned_handles += 1
        return (handle, camera_type, camera_name, camera_serial)

    def set_handle(self, handle):
        set_handle_params = SetDriverHandleParams(handle)
        self.send_command('CC_SET_DRIVER_HANDLE', params=set_handle_params)
        
    def query_temp_status(self, handle):
        self.set_handle(handle)
        
        query_temp_params = QueryTemperatureStatusParams(temp_status_request_codes['TEMP_STATUS_ADVANCED2'])
        query_temp_results = QueryTemperatureStatusResults2()
        self.send_command('CC_QUERY_TEMPERATURE_STATUS', query_temp_params, query_temp_results)

        return query_temp_results

    def set_temp_regulation(self, handle, set_point):
        self.set_handle(handle)

        if set_point:
            # Passed a True value as set_point, turn on cooling.
            enable_code = temperature_regulation_codes['REGULATION_ON']
        else:
            # Passed a False value as set_point, turn off cooling and reset
            # set point to +25 C
            enable_code = temperature_regulation_codes['REGULATION_OFF']
            set_point = 25.0
            
        set_temp_params = SetTemperatureRegulationParams2(enable_code, set_point)
        self.send_command('CC_SET_TEMPERATURE_REGULATION2', params = set_temp_params)
    
    def send_command(self, command, params=None, results=None):
        """
        Function for sending a command to the SBIG Universal Driver/Library.

        Args:
            command (string): Name of command to send
            params (ctypes.Structure, optional): Subclass of Structure
                                                 containing command parameters
            results (ctypes.Structure, optional): Subclass of Structure to
                                                  store command results

        Returns:
           int: return code from SBIG driver

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
            raise KeyError("Invalid SBIG command '{}'!".format(command))

        # Send the command to the driver. Need to pass pointers to params,
        # results structs or None (which gets converted to a null pointer).
        return_code = self._CDLL.SBIGUnivDrvCommand(command_code,
                                                    (ctypes.byref(params) if params else None),
                                                    (ctypes.byref(results) if results else None))

        # Look up the error message for the return code, raises Error is no
        # match found.
        try:
            error = errors[return_code]
        except KeyError:
            raise RuntimeError("SBIG Driver returned unknown error code '{}'".format(return_code))

        # Raise a RuntimeError exception if return code is not 0 (no error).
        # This is probably excessively cautious and will need to be relaxed,
        # there are likely to be situations where other return codes don't
        # necessarily indicate a fatal error.
        if error != 'CE_NO_ERROR':
            raise RuntimeError("SBIG Driver returned error '{}'!".format(error))

        return error

# Private methods

    def _get_library_path(self, library_path, library_name):
        """
        Constructs full path to SBIG library using OS specific defaults.
        """
        system_name = platform.system()

        if not library_path:
            if system_name == 'Linux':
                library_path = '/usr/local/lib/'
            elif system_name == 'Darwin':
                library_path = '/Library/Frameworks/SBIGUDrv.framework/'
            elif system_name == 'Windows':
                library_path = '/Windows/System/'
            else:
                raise RuntimeError('Unable to determine system OS, please specify library path & library name manually!')

        if not library_name:
            if system_name == 'Linux':
                library_name = 'libsbigudrv.so'
            elif system_name == 'Darwin':
                library_name = 'SBIGUDrv'
            elif system_name == 'Windows':
                library_name = 'SBIGUDRV.DLL'
            else:
                raise RuntimeError('Unable to determine system OS, please specify library path & library name manually!')

        return path.join(library_path, library_name)
