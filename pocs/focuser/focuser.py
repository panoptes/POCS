from .. import PanBase


class AbstractFocuser(PanBase):
    """
    Base class for all focusers
    """
    def __init__(self,
                 name='Generic Focuser',
                 model='simulator',
                 port=None,
                 camera=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name

        self._connected = False
        self._serial_number = 'XXXXXX'
        self._position = None

        self._camera = camera

        self.logger.debug('Focuser created: {} on {}'.format(self.name, self.port))

##################################################################################################
# Properties
##################################################################################################

    @property
    def uid(self):
        """ A serial number for the focuser """
        return self._serial_number

    @property
    def is_connected(self):
        """ Is the focuser available """
        return self._connected

    @property
    def position(self):
        """ Current encoder position of the focuser """
        return self._position

    @position.setter
    def position(self, position):
        """ Move focusser to new encoder position """
        self.move_to(position)

    @property
    def camera(self):
        """
        Reference to the Camera object that the Focuser is assigned to, if any. A Focuser
        should only ever be assigned to one or zero Cameras!
        """
        return self._camera

    @camera.setter
    def camera(self, camera):
        if self._camera:
            self.logger.error("{} already assigned to camera {}!".format(self, self.camera))
        else:
            self._camera = camera

##################################################################################################
# Methods
##################################################################################################

    def move_to(self, position):
        """ Move focusser to new encoder position """
        raise NotImplementedError

    def move_by(self, increment):
        """ Move focusser by a given amount """
        raise NotImplementedError

    def __str__(self):
        return "{} ({}) on {}".format(self.name, self.uid, self.port)
