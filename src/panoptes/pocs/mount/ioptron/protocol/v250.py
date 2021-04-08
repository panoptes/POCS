from enum import Enum


class SerialCommands250(Enum):
    # Information and settings.
    GET_STATUS = ('GLS', None, '{FULL_STATUS}')
    GET_TIME = ('GUT', None, '{UTC_OFFSET}{DST_ON}{UTC_TIME}')
    GET_POSITION = ('GEC', None, '{SIGN}{DEC_ARCSEC}{RA_ARCSEC}')
    GET_POSITION_ALTAZ = ('GAC', None, '{SIGN}{ALTITUDE_ARCSEC}{AZIMUTH_ARCSEC}')
    GET_PARKING_POSITION = ('GPC', None, '{ALTITUDE_ARCSEC}{AZIMUTH_ARCSEC}')
    GET_MAX_SLEW_SPEED = ('GSR', None, '{MAX_SLEW_SPEED}')
    GET_ALTITUDE_LIMIT = ('GAL', None, '{SIGN}{ALTITUDE_DEGREE}')
    GET_GUIDING_RATE = ('AG', None, '{RA_GUIDE_RATE}{DEC_GUIDE_RATE}')
    GET_MERIDIAN_TREATMENT = ('GMT', None, '{MERIDIAN_TREATMENT}{ALTITUDE_DEGREE}')

    # Change settings.
    SET_SIDEREAL_RATE = ('RT0', None, '{SUCCESS}')
    SET_LUNAR_RATE = ('RT1', None, '{SUCCESS}')
    SET_SOLAR_RATE = ('RT2', None, '{SUCCESS}')
    SET_KING_RATE = ('RT3', None, '{SUCCESS}')
    SET_CUSTOM_RATE = ('RT4', None, '{SUCCESS}')
    SET_MOVING_RATE = ('SR', '{SLEW_SPEED}', '{SUCCESS}')

    # Time settings.
    SET_UTC_OFFSET = ('SG', '{UTC_OFFSET}', '{SUCCESS}')
    SET_DST_ON = ('SDS1', None, '{SUCCESS}')
    SET_DST_OFF = ('SDS0', None, '{SUCCESS}')
    SET_LOCAL_DATE = ('SC', '{LOCAL_DATE}', '{SUCCESS}')
    SET_LOCAL_TIME = ('SL', '{LOCAL_TIME}', '{SUCCESS}')

    # Location settings.
    SET_LONGITUDE = ('Sgs', '{SIGN}{LONGITUDE}', '{SUCCESS}')
    SET_LATITUDE = ('Sts', '{SIGN}{LATITUDE}', '{SUCCESS}')
    SET_HEMISPHERE_NORTH = ('SHE0', None, '{SUCCESS}')
    SET_HEMISPHERE_SOUTH = ('SHE1', None, '{SUCCESS}')

    # Mount settings.
    SET_MAX_SLEW_SPEED = ('MSR', '{MAX_SLEW_SPEED}', '{SUCCESS}')
    SET_ALTITUDE_LIMIT = ('SAL', '{SIGN}{ALT_LIMIT}', '{SUCCESS}')
    SET_RA_GUIDE_RATE = ('RG', '{RA_GUIDE_RATE}{DEC_GUIDE_RATE}', '{SUCCESS}')
    SET_MERIDIAN_STOP = ('SMT0', '{ALT_LIMIT}', '{SUCCESS}')
    SET_MERIDIAN_FLIP = ('SMT1', '{ALT_LIMIT}', '{SUCCESS}')

    RESET_SETTINGS = ('RAS', None, '{SUCCESS}')

    # Telescope Motion.
    SLEW_TO_TARGET = ('MS', None, '{SUCCESS_OR_FAIL}')
    STOP = ('Q', None, '{SUCCESS}')
    SET_TRACKING_ON = ('ST1', None, '{SUCCESS}')
    SET_TRACKING_OFF = ('ST0', None, '{SUCCESS}')
    PARK = ('MP1', None, '{SUCCESS_OR_FAIL}')
    UNPARK = ('MP0', None, '{SUCCESS}')
    GOTO_HOME = ('MH', None, '{SUCCESS}')
    GOTO_ZERO = ('MH', None, '{SUCCESS}')
    FIND_HOME = ('MSH', None, '{SUCCESS}')
    SET_RA_TRACKING_RATE = ('RR', '{RA_TRACKING_RATE}', '{SUCCESS}')

    MOVE_BUTTON_NORTH = ('mn', None, None)
    MOVE_BUTTON_EAST = ('me', None, None)
    MOVE_BUTTON_SOUTH = ('ms', None, None)
    MOVE_BUTTON_WEST = ('mw', None, None)
    STOP_BUTTON_MOVE = ('q', None, '{SUCCESS}')
    STOP_LR_BUTTON_MOVE = ('qR', None, '{SUCCESS}')
    STOP_UD_BUTTON_MOVE = ('qD', None, '{SUCCESS}')

    # Telescope position.
    SYNC_MOUNT = ('CM', None, '{SUCCESS}')
    SET_RA = ('Sr', '{RA_ARCSEC}', '{SUCCESS}')
    SET_DEC = ('Sd', '{SIGN}{DEC_ARCSEC}', '{SUCCESS}')
    SET_AZIMUTH = ('Sz', '{RA_ARCSEC}', '{SUCCESS}')
    SET_ALTITUDE = ('Sa', '{SIGN}{DEC_ARCSEC}', '{SUCCESS}')
    SET_ZERO_POSITION = ('SZP', None, '{SUCCESS}')
    SET_PARKING_AZIMUTH = ('SPA', '{RA_ARCSEC}', '{SUCCESS}')
    SET_PARKING_ALTITUDE = ('SPH', '{DEC_ARCSEC}', '{SUCCESS}')

    # Hardware info.
    FIRMWARE_MAINBOARD = ('FW1', None, '{LOCAL_DATE}{LOCAL_DATE}')
    FIRMWARE_RADEC = ('FW2', None, '{LOCAL_DATE}{LOCAL_DATE}')
    MOUNT_INFO = ('MountInfo', None, '{MOUNT_VERSION')
