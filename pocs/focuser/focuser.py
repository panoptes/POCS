from .. import PanBase


class AbstractFocuser(PanBase):
    """
    Base class for all focusers
    """
    def __init__(self,
                 name='Generic Focuser',
                 model='simulator',
                 port=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.port = port
        self.name = name

        self._connected = False
        self._serial_number = 'XXXXXX'
        self._position = None

        self.logger.debug('Focuser created: {}'.format(self))

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
        return "{}({}) on {}".format(self.name, self.uid, self.port)
