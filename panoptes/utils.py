import time

from panoptes.utils.logger import Logger
from panoptes.utils.serial import SerialData
from panoptes.utils.convert import Convert

def get_logger():
    return Logger()

def get_serial():
    return SerialData()

def get_convert():
    return Conver()