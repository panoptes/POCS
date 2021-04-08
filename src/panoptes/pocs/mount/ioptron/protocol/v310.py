from enum import Enum


class SerialCommands310(Enum):
    # Information and settings.
    GET_STATUS = ('GLS', None, '{FULL_STATUS}')
    GET_TIME = ('GUT', None, '{UTC_OFFSET}{DST_ON}{UTC_TIME}')
    GET_POSITION = ('GEP', None, '{SIGN}{DEC_ARCSEC}{RA_ARCSEC}{PIER_SIDE}{POINTING_STATE}')
    GET_POSITION_ALTAZ = ('GAC', None, '{SIGN}{ALTITUDE_ARCSEC}{AZIMUTH_ARCSEC}')
    GET_PARKING_POSITION = ('GPC', None, '{ALTITUDE_ARCSEC}{AZIMUTH_ARCSEC}')
    GET_MAX_SLEW_SPEED = ('GSR', None, '{MAX_SLEW_SPEED}')
    GET_ALTITUDE_LIMIT = ('GAL', None, '{SIGN}{ALTITUDE_DEGREE}')
    GET_GUIDING_RATE = ('AG', None, '{RA_GUIDE_RATE}{DEC_GUIDE_RATE}')
    GET_MERIDIAN_TREATMENT = ('GMT', None, '{MERIDIAN_TREATMENT}{ALTITUDE_DEGREE}')

    GET_TRACKING_RATE = ('GTR', None, '{RA_TRACKING_RATE}')
    GET_PE_INTEGRITY = ('GPE', None, '{SUCCESS_OR_FAIL}')
    GET_PE_RECORDING = ('GPR', None, '{SUCCESS_OR_FAIL}')

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
    SET_UTC_TIME = ('SUT', '{UTC_TIME}', '{SUCCESS}')

    # Location settings.
    SET_LONGITUDE = ('SLO', '{SIGN}{LONGITUDE}', '{SUCCESS}')
    SET_LATITUDE = ('SLA', '{SIGN}{LATITUDE}', '{SUCCESS}')
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
    SLEW_TO_TARGET = ('MS1', None, '{SUCCESS_OR_FAIL}')
    ALT_SLEW_TO_TARGET = ('MS2', None, '{SUCCESS_OR_FAIL}')
    SLEW_TO_TARGET_ALTAZ = ('MSS', None, '{SUCCESS_OR_FAIL}')
    STOP = ('Q', None, '{SUCCESS}')
    SET_TRACKING_ON = ('ST1', None, '{SUCCESS}')
    SET_TRACKING_OFF = ('ST0', None, '{SUCCESS}')
    MOVE_RA_POSITIVE_SECONDS = ('ZS', '{MOVEMENT_MS}', None)
    MOVE_RA_NEGATIVE_SECONDS = ('ZQ', '{MOVEMENT_MS}', None)
    MOVE_DEC_POSITIVE_SECONDS = ('ZE', '{MOVEMENT_MS}', None)
    MOVE_DEC_NEGATIVE_SECONDS = ('ZC', '{MOVEMENT_MS}', None)

    PARK = ('MP1', None, '{SUCCESS_OR_FAIL}')
    UNPARK = ('MP0', None, '{SUCCESS}')
    GOTO_HOME = ('MH', None, '{SUCCESS}')
    GOTO_ZERO = ('MH', None, '{SUCCESS}')
    FIND_HOME = ('MSH', None, '{SUCCESS}')

    SET_RA_TRACKING_RATE = ('RR', '{RA_TRACKING_RATE}', '{SUCCESS}')
    START_PERIODIC_ERROR_RECORDING = ('SPR1', None, '{SUCCESS}')
    STOP_PERIODIC_ERROR_RECORDING = ('SPR0', None, '{SUCCESS}')
    START_PERIODIC_ERROR_PLAYBACK = ('SPP1', None, '{SUCCESS}')
    STOP_PERIODIC_ERROR_PLAYBACK = ('SPP0', None, '{SUCCESS}')

    MOVE_BUTTON_NORTH = ('mn', None, None)
    MOVE_BUTTON_EAST = ('me', None, None)
    MOVE_BUTTON_SOUTH = ('ms', None, None)
    MOVE_BUTTON_WEST = ('mw', None, None)
    STOP_BUTTON_MOVE = ('Q', None, '{SUCCESS}')
    STOP_LR_BUTTON_MOVE = ('qR', None, '{SUCCESS}')
    STOP_UD_BUTTON_MOVE = ('qD', None, '{SUCCESS}')

    # Telescope position.
    SYNC_MOUNT = ('CM', None, '{SUCCESS}')
    QUERY_POSITION = ('QAP', None, '{NUM_POSITIONS}')
    SET_RA = ('SRA', '{RA_ARCSEC}', '{SUCCESS}')
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
