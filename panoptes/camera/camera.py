import os
import sys
import re
import time
import datetime
import subprocess
import yaml

from ..utils.logger import has_logger
from ..utils.config import load_config
from ..utils import listify

@has_logger
class AbstractCamera(object):
    """ Abstract Camera class

    Args:
        name(str):      Name for the camera, defaults to 'GenericCamera'
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """
    pass

    def __init__(self, name='GenericCamera', config=dict()):
        self.config = load_config()
        # Create an object for just the mount config items
        self.camera_config = config if len(config) else dict()

        # Check the config for required items
        assert self.camera_config.get('port') is not None, self.logger.error(
            'No camera port specified, cannot create camera\n {}'.format(self.camera_config))

        # Get the model and port number
        model = self.camera_config.get('model')
        port = self.camera_config.get('port')
        self.port = port

        self.name = name
        self.model = model

        self.properties = None
        self.cooled = True
        self.cooling = False

        self.logger.info('Camera {} created on {}: {} {}'.format(name, port))

##################################################################################################
# Methods
##################################################################################################

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        """
        # Create an object for just the camera config items
        self.camera_config = config if len(config) else dict()
        self.filename_pattern = self.camera_config.get('filename_pattern')

##################################################################################################
# NotImplemented Methods
##################################################################################################

    def connect(self):
        """ Connection method for the camera. """
        raise NotImplementedError

    def command(self, command):
        """ Runs a command on the camera

        This should be the only user-accessible way to run commands on the camera.

        Args:
            command(List[str]):   Commands to be passed to the camera

        Returns:
            list:           UTF-8 decoded response from camera
        """
        raise NotImplementedError

    def load_properties(self):
        """ Load properties from the camera

        Reads all the configuration properties available via attached camera and populates
        a local list with these entries.
        """
        raise NotImplementedError

    def get_property(self, property):
        """ Get a value for the given property

        Args:
            property(str):      Property name

        Returns:
            list:               A list containing string responses from camera
        """
        raise NotImplementedError

    def set_property(self, property, value):
        """ Sets a property for the camera

        Args:
            property(str):  The property to set
            value(str):     The value to set for the property

        Returns:
            list:           Response from camera as list of lines
        """
        raise NotImplementedError

    def start_cooling(self):
        """ Starts cooling the camera """
        raise NotImplementedError
