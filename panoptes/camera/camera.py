import panoptes.utils.logger as logger

@logger.has_logger
class AbstractCamera:
    """
    Main camera class
    """

    def __init__(self):
        ## Properties for all cameras
        self.connected = False
        self.cooling = None
        self.cooled = None
        self.exposing = None

