from threading import Event
import math

from astropy import units as u

from pocs.filterwheel import AbstractFilterWheel
from pocs.camera.sbig import Camera as SBIGCamera


class FilterWheel(AbstractFilterWheel):
    """
    Class for SBIG filter wheels connected to the I2C port of an SBIG camera.

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.sbig.Camera): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
        serial_number (str): serial number of the filter wheel
    """
    def __init__(self,
                 name='SBIG Filter Wheel',
                 model='sbig',
                 camera=None,
                 filter_names=None,
                 serial_number=None,
                 *args, **kwargs):
        if camera is None:
            msg = "Camera must be provided for SBIG filter wheels"
            self.logger.error(msg)
            raise ValueError(msg)
        if not isinstance(camera, SBIGCamera):
            msg = "Camera must be an instance of pocs.camera.sbig.Camera, got {}".format(camera)
            self.logger.error(msg)
            raise ValueError(msg)
        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_name,
                         *args, **kwargs)
        self._serial_number = serial_number
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

        self.logger.info("Filter wheel {} initialised".format(self))
        self._connected = True

##################################################################################################
# Properties
##################################################################################################

    @property
    def firmware_version(self):
        """ Firmware version of the filter wheel """
        return self._firmware_version

    @property
    def position(self):
        """ Current integer position of the filter wheel """
        status = self._SBIGDriver.cfw_query(self._handle)
        if math.isnan(status['position']):
            self.logger.warning("Filter wheel position unknown, returning NaN")
        return status['position']

##################################################################################################
# Methods
##################################################################################################

    def move_to(self, position, blocking=False, timeout=10 * u.second):
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
        assert self.is_connected, self.logger.error("Filter wheel must be connected to move")
        position = self._parse_position(position)
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
        return "{} ({}) on {}".format(self.name, self.uid, self.camera.uid)
