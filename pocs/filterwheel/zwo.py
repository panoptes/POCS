import threading
import math

from astropy import units as u

from pocs.filterwheel import AbstractFilterWheel
from pocs.filterwheel.libefw import EFWDriver
from pocs.camera.camera import AbstractCamera


class FilterWheel(AbstractFilterWheel):
    """
    Class for ZWO filter wheels.

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.camera.AbstractCamera): camera that this filterwheel is associated with.
        filter_names (list of str): names of the filters installed at each filterwheel position
        timeout (u.Quantity, optional): maximum time to wait for a move to complete. Should be
            a Quantity with time units. If a numeric type without units is given seconds will be
            assumed. Default is 10 seconds.
        serial_number (str): serial number of the filter wheel
        library_path (str, optional): path to the library e.g. '/usr/local/lib/libASICamera2.so
    """

    _driver = None

    def __init__(self,
                 name='ZWO Filter Wheel',
                 model='sbig',
                 camera=None,
                 filter_names=None,
                 timeout=10 * u.second,
                 serial_number=None,
                 library_path=None,
                 *args, **kwargs):
        if camera and not isinstance(camera, AbstractCamera):
            msg = f"Camera must be an instance of pocs.camera.camera.AbstractCamera, got {camera}."
            self.logger.error(msg)
            raise ValueError(msg)
        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_names,
                         timeout=timeout,
                         serial_number=serial_number,
                         *args, **kwargs)

        if FilterWheel._driver is None:
            # Initialise the driver if it hasn't already been done
            FilterWheel._driver = EFWDriver(library_path=library_path)

        self.connect()

##################################################################################################
# Properties
##################################################################################################

    @AbstractFilterWheel.position.getter
    def position(self):
        """ Current integer position of the filter wheel """
        return self._driver.get_position(self._handle) + 1  # 1-based numbering

    @property
    def is_moving(self):
        """ Is the filterwheel currently moving """
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """Connect to filter wheel."""
        

        self._handle = self.camera._handle

        info = self._driver.cfw_get_info(self._handle)
        self._model = info['model']
        self._firmware_version = info['firmware_version']
        self._n_positions = info['n_positions']
        if len(self.filter_names) != self.n_positions:
            msg = "Number of names in filter_names ({}) doesn't".format(len(self.filter_names)) + \
                " match number of positions in filter wheel ({})".format(self.n_positions)
            self.logger.error(msg)
            raise ValueError(msg)

        self.logger.info("Filter wheel {} initialised".format(self))
        self._connected = True

    def recalibrate(self):
        """
        Reinitialises/recalibrates the filter wheel.
        """
        self._driver.calibrate(self._handle)
        self.logger.info("{} reinitialised".format(self))

##################################################################################################
# Private methods
##################################################################################################

    def _move_to(self, position, move_event):
        self._driver.set_position(self._handle, self._parse_position(position))
