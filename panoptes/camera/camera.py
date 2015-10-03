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
from ..utils.indi import PanIndiDevice

@has_logger
class AbstractCamera(PanIndiDevice):
    """
    Abstract Camera class
    """
    pass

    def __init__(self, name='GenericCamera', config=dict()):
        """
        Initialize the camera
        """
        super().__init__(name)

        self.config = load_config()
        # Create an object for just the mount config items
        self.camera_config = config if len(config) else dict()

        # Check the config for required items
        assert self.camera_config.get('port') is not None, self.logger.error(
            'No camera port specified, cannot create camera\n {}'.format(self.camera_config))

        # Get the model and port number
        model = self.camera_config.get('model')
        port = self.camera_config.get('port')
        self.logger.info('Creating camera: {} {}'.format(model, port))

        self.cooled = True
        self.cooling = False
        self.model = model
        self.USB_port = port
        self.name = None
        self.properties = None

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
            command(list):   Commands to be passed to the camera

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


    def get(self, property):
        """ Get a value for the given property

        Args:
            property(str):      Property name

        Returns:
            list:               A list containing string responses from camera
        """
        raise NotImplementedError

    def set(self, property, value):
        """ Sets a property for the camera

        Args:
            property(str):  The property to set
            value(str):     The value to set for the property

        Returns:
            list:           Response from camera as list of lines
        """
        raise NotImplementedError

    def get_iso(self):
        """
        Queries the camera for the ISO setting and populates the self.iso
        property with a string containing the ISO speed.

        Also examines the output of the command to populate the self.iso_options
        property which is a dictionary associating the iso speed (as a string)
        with the numeric value used as input for the set_iso() method.  The keys
        in this dictionary are the allowed values of the ISO for this camera.

        Returns:
            str:        The current ISO setting
        """
        raise NotImplementedError

    def set_iso(self, iso=100):
        """ Sets the ISO speed of the camera.

        Checks that the input value (a string or int) is in the list of allowed values in
        the self.iso_options dictionary.
        """
        raise NotImplementedError

    def get_serial_number(self):
        """
        Gets the generic Serial Number property and populates the
        self.serial_number property.

        Note: Some cameras override this. See `canon.get_serial_number`
        """
        raise NotImplementedError

    def get_model(self):
        """
        Gets the Camera Model string from the camera and populates the
        self.model property.
        """
        raise NotImplementedError

    def get_device_version(self):
        """
        Gets the Device Version string from the camera and populates the
        self.device_version property.
        """
        raise NotImplementedError

    def get_shutter_count(self):
        """
        Gets the shutter count value and populates the self.shutter_count
        property.
        """
        raise NotImplementedError

    def start_cooling(self):
        """
        This does nothing for a Canon DSLR as it does not have cooling.
        """
        raise NotImplementedError
