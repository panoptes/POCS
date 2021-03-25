from dataclasses import dataclass
import re
from enum import Enum
from typing import Union, Optional


@dataclass
class SerialCommand:
    """A dataclass for serial commands."""
    command: Union[str, re.Pattern]
    response: Union[bool, str]
    params: Optional[str] = None
    prefix: str = ':'
    postfix: str = '#'

    def __str__(self):
        return f'{self.prefix}{self.command}{self.postfix}'


class SerialParams(Enum):
    # TODO add capture groups.
    UTC_OFFSET = re.compile(r'\d{3}')
    UTC_TIME = re.compile(r'\d{13}')
    SIGN = re.compile(r'[+\-]')
    LONGITUDE = re.compile(r'\d{8}')
    LATITUDE = re.compile(r'\d{8}')
    SLEW_SPEED = re.compile(r'[789]')
    ALT_LIMIT = re.compile(r'\d{2}')
    RA_GUIDE_RATE = re.compile(r'\d{2}')
    DEC_GUIDE_RATE = re.compile(r'\d{2}')
    MOVEMENT_MS = re.compile(r'\d{5}')
    RA_TRACKING_RATE = re.compile(r'\d{5}')
    RA_ARCSEC = re.compile(r'\d{9}')
    DEC_ARCSEC = re.compile(r'\d{8}')
    SYSTEM_STATUS = re.compile(r'\d{6}')
    DST_ON = re.compile(r'[01]')
    PIER_SIDE = re.compile(r'[012]')
    POINTING_STATE = re.compile(r'[01]')


class SerialCommands310(Enum):
    # Information and settings.
    GET_STATUS = ('GLS', None, '{LONGITUDE}{LATITUDE}{SYSTEM_STATUS}')
    GET_TIME = ('GUT', None, '{SIGN}{UTC_OFFSET}{DST_ON}{UTC_TIME}')
    GET_POSITION = ('GEP', None, '{SIGN}{DEC_ARCSEC}{RA_ARCSEC}{PIER_SIDE}{POINTING_STATE}')
    GET_POSITION_ALTAZ = 'GAC'
    GET_TRACKING_RATE = 'GTR'
    GET_PARKING_POSITION = 'GPC'
    GET_MAX_SLEW_SPEED = 'GSR'
    GET_ALTITUDE_LIMIT = 'GAL'
    GET_GUIDING_RATE = 'AG'
    GET_MERIDIAN_TREATMENT = 'GMT'
    GET_PE_INTEGRITY = 'GPE'
    GET_PE_RECORDING = 'GPR'

    # Change settings.
    SET_SIDEREAL_RATE = 'RT0'
    SET_LUNAR_RATE = 'RT1'
    SET_SOLAR_RATE = 'RT2'
    SET_KING_RATE = 'RT3'
    SET_CUSTOM_RATE = 'RT4'
    SET_MOVING_RATE = 'SRn'

    # Time settings.
    SET_UTC_OFFSET = 'SG{SIGN}{UTC_OFFSET}'
    SET_DST_ON = 'SDS1'
    SET_DST_OFF = 'SDS0'
    SET_UTC_TIME = 'SUT{UTC_TIME}'

    # Location settings.
    SET_LONGITUDE = 'SLO{SIGN}{LONGITUDE}'
    SET_LATITUDE = 'SLA{SIGN}{LATITUDE}'
    SET_HEMISPHERE_NORTH = 'SHE0'
    SET_HEMISPHERE_SOUTH = 'SHE1'

    # Mount settings.
    SET_MAX_SLEW_SPEED = 'MSR{SLEW_SPEED}'
    SET_ALTITUDE_LIMIT = 'SAL{SIGN}{ALT_LIMIT}'
    SET_RA_GUIDE_RATE = 'RG{RA_GUIDE_RATE}{DEC_GUIDE_RATE}'
    SET_MERIDIAN_STOP = 'SMT0{ALT_LIMIT}'
    SET_MERIDIAN_FLIP = 'SMT1{ALT_LIMIT}'

    RESET_SETTINGS = 'RAS'

    # Telescope Motion.
    STOP = 'Q'
    SLEW_TO_TARGET = 'MS1'
    SLEW_TO_TARGET_COUNTERWEIGHT_UP = 'MS2'
    SLEW_TO_ALTAZ = 'MSS'
    SET_TRACKING_ON = 'ST1'
    SET_TRACKING_OFF = 'ST0'
    MOVE_RA_POSITIVE_SECONDS = 'ZS{MOVEMENT_MS}'
    MOVE_RA_NEGATIVE_SECONDS = 'ZQ{MOVEMENT_MS}'
    MOVE_DEC_POSITIVE_SECONDS = 'ZE{MOVEMENT_MS}'
    MOVE_DEC_NEGATIVE_SECONDS = 'ZC{MOVEMENT_MS}'
    PARK = 'MP1'
    UNPARK = 'MP0'
    GOTO_HOME = 'MH'
    GOTO_ZERO = 'MH'
    FIND_HOME = 'MSH'
    STOP_PE_RECORDING = 'SPR0'
    START_PE_RECORDING = 'SPR1'
    SET_PE_PLAYBACK_OFF = 'SPP0'
    SET_PE_PLAYBACK_ON = 'SPP1'
    SET_RA_TRACKING_RATE = 'RR{RA_TRACKING_RATE}'

    # Telescope position.
    SYNC_MOUNT = 'CM'
    GET_POSSIBLE_POSITIONS = 'QAP'
    SET_RA = 'SRA{RA_ARCSEC}'
    SET_AZIMUTH = 'Sz{RA_ARCSEC}'
    SET_DEC = 'Sd{SIGN}{DEC_ARCSEC}'
    SET_ALTITUDE = 'Sa{SIGN}{DEC_ARCSEC}'
    SET_ZERO_POSITION = 'SZP'
    SET_PARKING_AZIMUTH = 'SPA{RA_ARCSEC}'
    SET_PARKING_ALTITUDE = 'SPH{DEC_ARCSEC}'  # No sign?

    # Hardware info.
    FIRMWARE_MOTOR = 'FW1'
    FIRMWARE_RADEC = 'FW2'
    MOUNT_INFO = 'MountInfo'
