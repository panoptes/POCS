from pocs.base import PanBase


class AbstractFilterWheel(PanBase):
    """
    Base class for all filter wheels

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.Camera, optional): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
    """
    def __init__(self,
                 name='Generic Filter Wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._model = model
        self._name = name
        self._camera = camera
        self._filter_names = filter_names

        self._n_positions = len(filter_names)
        self._connected = False
        self._serial_number = 'XXXXXX'

        self.logger.debug('Filter wheel created: {}'.format(self))

##################################################################################################
# Properties
##################################################################################################

    @property
    def model(self):
        """ Model of the filter wheel """
        return self._model

    @property
    def name(self):
        """ Name of the filter wheel """
        return self._name

    @property
    def uid(self):
        """ A serial number of the filter wheel """
        return self._serial_number

    @property
    def is_connected(self):
        """ Is the filterwheel available """
        return self._connected

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
            self.logger.warning("{} assigned to {}, skipping attempted assignment to {}!",
                                self, self.camera, camera)
        else:
            self._camera = camera

    @property
    def filter_names(self):
        """ List of the names of the filters installed in the filter wheel """
        return self._filter_names

    @property
    def n_positions(self):
        """ Number of positions in the filter wheel """
        return self._n_positions

##################################################################################################
# Methods
##################################################################################################

    def move_to(self, position, blocking=False):
        """
        Move the filter wheel to the given position.

        The position can be expressed either as an integer, or as (part of) one of the names from
        the filter_names list. To allow filter names of the form '<filter band>_<serial number>'
        to be selected by band only position can be a substring from the start of one
        of the names in the filter_names list, provided that this produces only one match.

        Args:
            position (int or str): position to move to.
            blocking (bool, optional): If False (default) return immediately, if True block until
                the filter wheel move has been completed.

        Returns:
            threading.Event: Event that will be set to signal when the move has completed
        """
        raise NotImplementedError

##################################################################################################
# Private methods
##################################################################################################

    def _fits_header(self, header):
        header.set('FW-NAME', self.name, 'Filter wheel name')
        header.set('FW-MOD', self.model, 'Filter wheel model')
        header.set('FW-ID', self.uid, 'Filter wheel serial number')
        header.set('FW-POS', self.position, 'Filter wheel position')
        header.set('FILTER', self.filter_name, 'Filter name')
        return header

    def __str__(self):
        return "{} ({})".format(self.name, self.uid)
