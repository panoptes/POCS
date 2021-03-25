from enum import IntEnum, Enum
from astropy import units as u


class MountConstants(Enum):
    SIDEREAL_RATE = ((360 * u.degree).to(u.arcsec) / (86164 * u.second))


class SerialParams(Enum):
    UTC_OFFSET = r'(?P<utc_offset>\d{3})'
    UTC_TIME = r'(?P<utc_time>\d{13})'
    SIGN = r'(?P<sign>[+\-])'
    LONGITUDE = r'(?P<longitude>[+\-]\d{8})'
    LATITUDE = r'(?P<latitude>\d{8})'
    SLEW_SPEED = r'(?P<slew_speed>[789])'
    ALT_LIMIT = r'(?P<alt_limit>\d{2})'
    RA_GUIDE_RATE = r'(?P<ra_guide_rate>\d{2})'
    DEC_GUIDE_RATE = r'(?P<dec_guide_rate>\d{2})'
    MOVEMENT_MS = r'(?P<movement_ms>\d{5})'
    RA_TRACKING_RATE = r'(?P<ra_tracking_rate>\d{5})'
    RA_ARCSEC = r'(?P<ra_arcsec>\d{9})'
    DEC_ARCSEC = r'(?P<dec_arcsec>[+\-]\d{8})'
    POINTING_STATE = r'(?P<pointing_state>[01])'
    DST_ON = r'(?P<dst_on>[01])'
    PIER_SIDE = r'(?P<pier_side>[0-2])'
    GPS_STATUS = r'(?P<gps_status>[0-2])'
    SYSTEM_STATUS = r'(?P<system_status>[0-7])'
    TRACKING_STATUS = r'(?P<tracking_status>[0-4])'
    MOVEMENT_STATUS = r'(?P<movement_status>[0-9])'
    TIME_SOURCE = r'(?P<time_source>[1-3])'
    HEMISPHERE = r'(?P<hemisphere>[01])'
    FULL_STATUS = LONGITUDE + LATITUDE + GPS_STATUS + SYSTEM_STATUS + \
        TRACKING_STATUS + MOVEMENT_STATUS + TIME_SOURCE + HEMISPHERE


class GPS(IntEnum):
    OFF = 0
    NO_DATA = 1
    DATA = 2


class SystemStatus(IntEnum):
    STOPPED_NO_ZERO = 0
    TRACKING_PEC_DISABLED = 1
    SLEWING = 2
    GUIDING = 3
    MERIDIAN_FLIPPING = 4
    TRACKING_PEC_ENABLED = 5
    PARKED = 6
    STOPPED_ZERO = 7


class TrackingStatus(IntEnum):
    SIDEREAL = 0
    LUNAR = 1
    SOLAR = 2
    KING = 3
    CUSTOM = 4


class MovementSpeedStatus(IntEnum):
    SIDEREAL_1X = 1
    SIDEREAL_2X = 2
    SIDEREAL_8X = 3
    SIDEREAL_16X = 4
    SIDEREAL_64X = 5
    SIDEREAL_128X = 6
    SIDEREAL_256X = 7
    SIDEREAL_512X = 8
    SIDEREAL_MAX = 9


class TimeSource(IntEnum):
    SERIAL = 1
    HAND_CONTROLLER = 2
    GPS = 3


class Hemisphere(IntEnum):
    SOUTHERN = 0
    NORTHERN = 1
