from enum import Enum


class SerialCommands310(Enum):
    PREFIX = ':'
    POSTFIX = '#'

    # Information and settings.
    GET_STATUS = 'GLS'
    GET_TIME = 'GUT'
    GET_POSITION = 'GEP'
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
    SET_UTC_OFFSET = 'SGsmmm'
    SET_DST_ON = 'SDS1'
    SET_DST_OFF = 'SDS0'
    SET_UTC_TIME = 'SUTxxxxxxxxxxxxx'

    # Location settings.
    SET_LONGITUDE = 'SLOstttttttt'
    SET_LATITUDE = 'SLAstttttttt'
    SET_HEMISPHERE_NORTH = 'SHE0'
    SET_HEMISPHERE_SOUTH = 'SHE1'

    # Mount settings.
    SET_MAX_SLEW_SPEED = 'MSRn'
    SET_ALTITUDE_LIMIT = 'SALsnn'
    SET_RA_GUIDE_RATE = 'RGnnnn'
    SET_MERIDIAN_TREAMENT = 'SMTnnn'

    RESET_SETTINGS = 'RAS'

    # Telescope Motion.
    STOP = 'Q'
    SLEW_TO_TARGET = 'MS1'
    SLEW_TO_TARGET_COUNTERWEIGHT_UP = 'MS2'
    SLEW_TO_ALTAZ = 'MSS'
    SET_TRACKING_ON = 'ST1'
    SET_TRACKING_OFF = 'ST0'
    MOVE_RA_POSITIVE_SECONDS = 'ZSxxxxx'
    MOVE_RA_NEGATIVE_SECONDS = 'ZQxxxxx'
    MOVE_DEC_POSITIVE_SECONDS = 'ZExxxxx'
    MOVE_DEC_NEGATIVE_SECONDS = 'ZCxxxxx'
    PARK = 'MP1'
    UNPARK = 'MP0'
    GOTO_HOME = 'MH'
    GOTO_ZERO = 'MH'
    FIND_HOME = 'MSH'
    STOP_PE_RECORDING = 'SPR0'
    START_PE_RECORDING = 'SPR1'
    SET_PE_PLAYBACK_OFF = 'SPP0'
    SET_PE_PLAYBACK_ON = 'SPP1'
    SET_RA_TRACKING_RATE = 'RRnnnnn'

    # Telescope position.
    SYNC_MOUNT = 'CM'
    GET_POSSIBLE_POSITIONS = 'QAP'
    SET_RA = 'SRAttttttttt'
    SET_DEC = 'Sdstttttttt'
    SET_ALTITUDE = 'Sastttttttt'
    SET_AZIMUTH = 'Szsttttttttt'
    SET_ZERO_POSITION = 'SZP'
    SET_PARKING_AZIMUTH = 'SPAttttttttt'
    SET_PARKING_ALTITUDE = 'SPAtttttttt'

    # Hardware info.
    FIRMWARE_MOTOR = 'FW1'
    FIRMWARE_RADEC = 'FW2'
    MOUNT_INFO = 'MountInfo'
