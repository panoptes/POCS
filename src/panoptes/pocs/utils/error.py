from panoptes.utils.error import *


class PocsError(PanError):
    """ Error for a POCS level exception """

    def __init__(self, msg='Problem with POCS', **kwargs):
        super().__init__(msg, **kwargs)


class CameraBusy(PocsError):
    """ A camera is already busy. """

    def __init__(self, msg='Camera busy.', **kwargs):
        super().__init__(msg, **kwargs)


class ImageSaturated(PocsError):
    """ An image is saturated. """

    def __init__(self, msg='Image is saturated', **kwargs):
        super().__init__(msg, **kwargs)


class BelowMinExptime(PocsError):
    """ An invalid exptime for a camera, too low. """

    def __init__(self, msg='Exposure time is too low for camera.', **kwargs):
        super().__init__(msg, **kwargs)


class AboveMaxExptime(PocsError):
    """ An invalid exptime for a camera, too high. """

    def __init__(self, msg='Exposure time is too high for camera.', **kwargs):
        super().__init__(msg, **kwargs)


class NotTwilightError(PanError):
    """ Error for when taking twilight flats and not twilight. """

    def __init__(self, msg='Not twilight', **kwargs):
        super().__init__(msg, **kwargs)


class NotSafeError(PanError):
    """ Error for when safety fails. """

    def __init__(self, msg='Not safe', **kwargs):
        super().__init__(msg, **kwargs)
