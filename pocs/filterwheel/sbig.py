from threading import Event

from astropy import units as u

from pocs.camera import AbstractCamera
from pocs.filterwheel import AbstractFilterWheel


class FilterWheel(AbstractFilterWheel):
    """

    """
    def __init__(self,
                 name='SBIG Filter Wheel',
                 model='sbig',
                 camera=None,
                 filter_names=None,
                 serial_number=None,
                 *args, **kwargs):
        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_name,
                         *args, **kwargs)

        if camera is None:
            msg = "Camera must be provided for SBIG filter wheels"
            self.logger.error(msg)
            raise ValueError(msg)
        if not isinstance(camera, AbstractCamera):
            msg = "Camera must be an instance of pocs.camera.AbstractCamera, got {}".format(camera)
            self.logger.error(msg)
            raise ValueError(msg)
        self._SBIGDriver = self.camera._SBIGDriver
        self._handle = self.camera._handle

        info = self._SBIGDriver.cfw_get_info(self._handle)
        self._firmware_version = info['firmware_version']
        self._n_positions = info['n_positions']
        if len(filter_names) != self.n_positions:
            msg = "Number of names in filter_names ({}) doesn't match".format(len(filter_names)) + \
                "number of positions in filter wheel ({})".format(self.n_positions)
            self.logger.error(msg)
            raise ValueError(msg)

##################################################################################################
# Properties
##################################################################################################

    @property
    def firmware_version(self):
        """ Firmware version of the filter wheel """
        return self._firmware_version

##################################################################################################
# Methods
##################################################################################################

    def go_to(self, position, blocking=False, timeout=10 * u.second):
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
            timeout (u.Quantity, optional): maximum time to wait for the move to complete. Should be
                a Quantity with time units. If a numeric type without units is given seconds will be
                assumed. Default is 10 seconds.

        Returns:
            threading.Event: Event that will be set to signal when the move has completed
        """
        move_event = Event()
        self._SBIGDriver.cfw_goto(handle=self._handle,
                                  position=position,
                                  cfw_event=move_event,
                                  timeout=timeout)
        if blocking:
            move_event.wait()

        return move_event

##################################################################################################
# Private methods
##################################################################################################

    def _fits_header(self, header):
        header = super()._fits_header(header)
        header.set('FW-FW', self.firmware_version, 'Filter wheel firmware version')
        return header

    def __str__(self):
        return "{} ({}) on {}".format(self.name, self.model, self.camera.uid)
