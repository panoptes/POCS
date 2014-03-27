
import time

from panoptes.utils import *

class PanoptesUtils():
    """
    Base class for all our utils functions. Currently provides:
        - self.logger   Logging methods
        - self.serial   Serial Port communication methods
        - self.convert  Convenience conversion methods
    """

    def __init__(self):
        """
        Sets up all utils
        """
        self.logger = Logger()
        self.serial = SerialData()
        self.convert = Convert()