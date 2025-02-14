from enum import IntEnum


class MountInfo(IntEnum):
    """The return type given by the MountInfo command to identify the mount."""
    HAE16 = 12
    CEM25 = 25
    CEM26 = 26
    CEM26EC = 27
    GEM28 = 28
    GEM28EC = 29
    iEQ30Pro = 30
    CEM40 = 40
    CEM40EC = 41
    GEM45 = 43
    GEM45EC = 44
    iEQ45Pro = 45
    iEQ45ProAA = 46
    CEM60 = 60
    CEM60EC = 61
    CEM70 = 70
    CEM70EC = 71
    CEM120 = 120
    CEM120EC = 121
    CEM120EC2 = 122


class MountGPS(IntEnum):
    OFF = 0
    ON = 1
    EXTRACTED = 2


class MountState(IntEnum):
    STOPPED = 0
    TRACKING = 1
    SLEWING = 2
    GUIDING = 3
    MERIDIAN_FLIPPING = 4
    TRACKING_PEC = 5
    PARKED = 6
    AT_HOME = 7
    UNKNOWN = 8


class MountTrackingState(IntEnum):
    SIDEREAL = 0
    LUNAR = 1
    SOLAR = 2
    KING = 3
    CUSTOM = 4


class MountMovementSpeed(IntEnum):
    SIDEREAL_1 = 1
    SIDEREAL_2 = 2
    SIDEREAL_8 = 3
    SIDEREAL_16 = 4
    SIDEREAL_64 = 5
    SIDEREAL_128 = 6
    SIDEREAL_256 = 7
    SIDEREAL_512 = 8
    SIDEREAL_MAX = 9


class MountTimeSource(IntEnum):
    RS232 = 1
    HAND_CONTROLLER = 2
    GPS = 3


class MountHemisphere(IntEnum):
    SOUTHERN = 0
    NORTHERN = 1
