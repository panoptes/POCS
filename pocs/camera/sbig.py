"""
Low level interface to the SBIG Unversal Driver/Library.

Reproduces in Python (using ctypes) the C interface provided by SBIG's shared library, i.e. 1 function that does 72 different things 
selected by passing an integer as the first argument. This is basically a direct translation of the enums and structs defined in the 
library C-header to Python dicts and ctypes.Structures, plus a very simple class (SBIGDriver) to load the library and call the single 
command function (SBIGDriver.send_command()).
"""
import platform
import ctypes
from os import path

# Camera command codes. Doesn't include the 'SBIG only" commands.
command_codes = {'CC_NULL': 0, \
                 'CC_START_EXPOSURE': 1, \
                 'CC_END_EXPOSURE': 2, \
                 'CC_READOUT_LINE': 3, \
                 'CC_DUMP_LINES': 4, \
                 'CC_SET_TEMPERATURE_REGULATION': 5, \
                 'CC_QUERY_TEMPERATURE_STATUS': 6, \
                 'CC_ACTIVATE_RELAY': 7, \
                 'CC_PULSE_OUT': 8, \
                 'CC_ESTABLISH_LINK': 9, \
                 'CC_GET_DRIVER_INFO': 10, \
                 'CC_GET_CCD_INFO': 11, \
                 'CC_QUERY_COMMAND_STATUS': 12, \
                 'CC_MISCELLANEOUS_CONTROL': 13, \
                 'CC_READ_SUBTRACT_LINE': 14, \
                 'CC_UPDATE_CLOCK': 15, \
                 'CC_READ_OFFSET': 16, \
                 'CC_OPEN_DRIVER': 17, \
                 'CC_CLOSE_DRIVER': 18, \
                 'CC_TX_SERIAL_BYTES': 19, \
                 'CC_GET_SERIAL_STATUS': 20, \
                 'CC_AO_TIP_TILT': 21, \
                 'CC_AO_SET_FOCUS': 22, \
                 'CC_AO_DELAY': 23, \
                 'CC_GET_TURBO_STATUS': 24, \
                 'CC_END_READOUT': 25, \
                 'CC_GET_US_TIMER': 26, \
                 'CC_OPEN_DEVICE': 27, \
                 'CC_CLOSE_DEVICE': 28, \
                 'CC_SET_IRQL': 29, \
                 'CC_GET_IRQL': 30, \
                 'CC_GET_LINE': 31, \
                 'CC_GET_LINK_STATUS': 32, \
                 'CC_GET_DRIVER_HANDLE': 33, \
                 'CC_SET_DRIVER_HANDLE': 34, \
                 'CC_START_READOUT': 35, \
                 'CC_GET_ERROR_STRING': 36, \
                 'CC_SET_DRIVER_CONTROL': 37, \
                 'CC_GET_DRIVER_CONTROL': 38, \
                 'CC_USB_AD_CONTROL': 39, \
                 'CC_QUERY_USB': 40, \
                 'CC_GET_PENTIUM_CYCLE_COUNT': 41, \
                 'CC_RW_USB_I2C': 42, \
                 'CC_CFW': 43, \
                 'CC_BIT_IO': 44, \
                 'CC_USER_EEPROM': 45, \
                 'CC_AO_CENTER': 46, \
                 'CC_BTDI_SETUP': 47, \
                 'CC_MOTOR_FOCUS': 48, \
                 'CC_QUERY_ETHERNET': 49, \
                 'CC_START_EXPOSURE2': 50, \
                 'CC_SET_TEMPERATURE_REGULATION2': 51, \
                 'CC_READ_OFFSET2': 52, \
                 'CC_DIFF_GUIDER': 53, \
                 'CC_COLUMN_EEPROM': 54, \
                 'CC_CUSTOMER_OPTIONS': 55, \
                 'CC_DEBUG_LOG': 56, \
                 'CC_QUERY_USB2': 57, \
                 'CC_QUERY_ETHERNET2': 58, \
                }

# Reversed dictionary, just in case you ever need to look up a command given a command code.
commands = {code: command for command, code in command_codes.items()}

# Camera error messages
errors = {0: 'CE_NO_ERROR', \
          1: 'CE_CAMERA_NOT_FOUND', \
          2: 'CE_EXPOSURE_IN_PROGRESS', \
          3: 'CE_NO_EXPOSURE_IN_PROGRESS', \
          4: 'CE_UNKNOWN_COMMAND', \
          5: 'CE_BAD_CAMERA_COMMAND', \
          6: 'CE_BAD_PARAMETER', \
          7: 'CE_TX_TIMEOUT', \
          8: 'CE_RX_TIMEOUT', \
          9: 'CE_NAK_RECEIVED', \
          10: 'CE_CAN_RECEIVED', \
          11: 'CE_UNKNOWN_RESPONSE', \
          12: 'CE_BAD_LENGTH', \
          13: 'CE_AD_TIMEOUT', \
          14: 'CE_KBD_ESC', \
          15: 'CE_CHECKSUM_ERROR', \
          16: 'CE_EEPROM_ERROR', \
          17: 'CE_SHUTTER_ERROR', \
          18: 'CE_UNKNOWN_CAMERA', \
          19: 'CE_DRIVER_NOT_FOUND', \
          20: 'CE_DRIVER_NOT_OPEN', \
          21: 'CE_DRIVER_NOT_CLOSED', \
          22: 'CE_SHARE_ERROR', \
          23: 'CE_TCE_NOT_FOUND', \
          24: 'CE_AO_ERROR', \
          25: 'CE_ECP_ERROR', \
          26: 'CE_MEMORY_ERROR', \
          27: 'CE_DEVICE_NOT_FOUND', \
          28: 'CE_DEVICE_NOT_OPEN', \
          29: 'CE_DEVICE_NOT_CLOSED', \
          30: 'CE_DEVICE_NOT_IMPLEMENTED', \
          31: 'CE_DEVICE_DISABLED', \
          32: 'CE_OS_ERROR', \
          33: 'CE_SOCK_ERROR', \
          34: 'CE_SERVER_NOT_FOUND', \
          35: 'CE_CFW_ERROR', \
          36: 'CE_MF_ERROR', \
          37: 'CE_FIRMWARE_ERROR', \
          38: 'CE_DIFF_GUIDER_ERROR', \
          39: 'CE_RIPPLE_CORRECTION_ERROR', \
          40: 'CE_EZUSB_RESET', \
          41: 'CE_NEXT_ERROR', \
         }

# Reverse dictionary, just in case you ever need to look up an error code given an error name
error_codes = {error: error_code for error_code, error in errors.items()}

class QUERY_USB_INFO(ctypes.Structure):
    """
    ctypes (Sub-)structure used to hold details of individual cameras returned by 'CC_QUERY_USB' command
    """
    _fields_ = [('cameraFound', ctypes.c_bool), \
                ('cameraType', ctypes.c_ushort), \
                ('name', ctypes.c_char * 64), \
                ('serialNumber', ctypes.c_char * 10)]

class QueryUSBResults(ctypes.Structure):
    """
    ctypes Structure used to hold the results from 'CC_QUERY_USB' command
    """
    _fields_ = [('camerasFound', ctypes.c_ushort), \
                ('usbInfo', QUERY_USB_INFO * 4),]

class SBIGDriver:
    def __init__(self, library_path=False, library_name=False):
        """
        Main class representing the SBIG Universal Driver/Library interface. On construction
        loads SBIG's shared library which must have already been installed (see 
        http://archive.sbig.com/sbwhtmls/devsw.htm). The name and location of the shared library
        can be manually specified with the library_path and library_name arguments, otherwise
        will try OS specific defaults.

        Args:
            library_path (string, optional): shared library path, e.g. '/usr/local/lib/' 
            library_name (string, optional): shared library name, e.g. 'lubsbigudrv.so'

        Returns:
            `~pocs.camera.sbig.SBIGDriver`
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

        self._sbig = ctypes.CDLL(path.join(library_path, library_name))
        
    def send_command(self, command, params=None, results=None):
        """
        Function for sending a command to the SBIG Universal Driver/Library.

        Args:
            command (string): Name of command to send 
            params (ctypes.Structure, optional): Subclass of Structure containing command parameters 
            results (ctypes.Structure, optional): Subclass of Structure to store command results

        Returns:
           int: return code from SBIG driver

        Raises:
           KeyError: Raised if command not in SBIG command list
           RuntimeError: Raised if return code indicates a fatal error, or is not recognised
        """
        # Look up integer command code for the given command string, raises KeyError
        # is no matches found.
        try:
            command_code = command_codes[command]
        except KeyError:
            raise KeyError("Invalid SBIG command '{}'!".format(command))

        # Send the command to the driver
        return_code = self._sbig.SBIGUnivDrvCommand(command_code, params, results)

        # Look up the error message for the return code, raises Error is no match found.
        try:
            error = errors[return_code]
        except KeyError:
            raise RuntimeError("SBIG Driver returned unknown error code '{}'".format(return_code))

        # Raise a RuntimeError exception if return code is not 0 (no error). This is probably
        # excessively cautious and will need to be relaxed, there are likely to be situations
        # where other return codes don't necessarily indicate a fatal error.
        if error != 'CE_NO_ERROR':
            raise RuntimeError("SBIG Driver returned error '{}'!".format(error))

        return return_code
