from contextlib import suppress

from astropy import units as u

from panoptes.pocs.filterwheel import AbstractFilterWheel
from panoptes.pocs.filterwheel.libefw import EFWDriver
from panoptes.pocs.camera.camera import AbstractCamera
from panoptes.utils import error


class FilterWheel(AbstractFilterWheel):
    """
    Class for ZWO filter wheels.

    Args:
        name (str, optional): name of the filter wheel.
        model (str, optional): model of the filter wheel.
        camera (pocs.camera.camera.AbstractCamera): camera that this filterwheel is associated with.
        filter_names (list of str): names of the filters installed at each filterwheel position.
        timeout (u.Quantity, optional): maximum time to wait for a move to complete. Should be
            a Quantity with time units. If a numeric type without units is given seconds will be
            assumed. Default is 10 seconds.
        serial_number (str): serial number of the filter wheel.
        library_path (str, optional): path to the library e.g. '/usr/local/lib/libASICamera2.so'.
        unidirectional (bool, optional): If True filterwheel will only rotate in one direction, if
            False filterwheel will move in either to get to the requested position via the
            shortest path. Default is True in order to improve repeatability.
        device_name (str, optional): If multiple filterwheels are connected to a single computer
            'device name' (e.g. 'EFW_7_0') can be used to select the desired one. See docstring
            of `pocs.filterwheel.libefw.EFWDriver.get_devices()` for details.
        initial_filter (str or int): Name of filter (or integer position) to move to when
            initialising filter.
    """

    _driver = None
    _filter_wheels = {}
    _assigned_filterwheels = set()

    def __init__(self,
                 name='ZWO Filter Wheel',
                 model='zwo',
                 camera=None,
                 filter_names=None,
                 timeout=10 * u.second,
                 serial_number=None,
                 library_path=None,
                 unidirectional=True,
                 device_name=None,
                 initial_filter=None,
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

        self._device_name = device_name
        self.connect()
        self.is_unidirectional = unidirectional
        if initial_filter:
            self.move_to(initial_filter, blocking=True)

    def __del__(self):
        """Attempt some clean up."""
        with suppress(AttributeError):
            device_name = self._device_name
            FilterWheel._assigned_filterwheels.discard(device_name)
            self.logger.debug('Removed {} from assigned filterwheels list'.format(device_name))

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
        return not self._move_event.is_set()

    @property
    def is_unidirectional(self):
        return self._driver.get_direction(self._handle)

    # ZWO filterwheels can be set to be unidirectional or bidirectional.
    @is_unidirectional.setter
    def is_unidirectional(self, unidirectional):
        self._driver.set_direction(self._handle, bool(unidirectional))

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """Connect to filter wheel."""
        if self.is_connected:
            self.logger.warning("Already connected.")
            return

        # Scan for connected filterwheels. This needs to be done at least once before
        # opening a connectio.
        FilterWheel._filterwheels = self._driver.get_devices()

        if len(FilterWheel._filterwheels) == 0:
            msg = "No ZWO filterwheels found."
            self.logger.error(msg)
            raise error.NotFound(msg)

        if self._device_name:
            self.logger.debug(f"Looking for filterwheel with device name '{self._device_name}'.")
            if self._device_name not in FilterWheel._filterwheels:
                msg = f"No filterwheel with device name '{self._device_name}'."
                self.logger.error(msg)
                raise error.NotFound(msg)
            if self._device_name in FilterWheel._assigned_filterwheels:
                msg = f"Filterwheel '{self._device_name}' already in use."
                self.logger.error(msg)
                raise error.PanError(msg)
        else:
            self.logger.debug("No device name specified, claiming 1st available filterwheel.")
            for device_name in FilterWheel._filterwheels:
                if device_name not in FilterWheel._assigned_filterwheels:
                    self._device_name = device_name
                    break
            if not self._device_name:
                msg = "All filterwheels already in use."
                self.logger.error(msg)
                raise error.PanError(msg)

        self.logger.debug(f"Claiming filterwheel '{self._device_name}'.")
        FilterWheel._assigned_filterwheels.add(self._device_name)
        self._handle = FilterWheel._filterwheels[self._device_name]
        self._driver.open(self._handle)
        info = self._driver.get_property(self._handle)
        self._model = info['name']
        self._n_positions = info['slot_num']

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
        self.logger.info("{} recalibrated".format(self))

##################################################################################################
# Private methods
##################################################################################################

    def _move_to(self, position):
        # Filterwheel class used 1 based position numbering,
        # ZWO EFW driver uses 0 based position numbering.
        self._driver.set_position(filterwheel_ID=self._handle,
                                  position=self._parse_position(position) - 1,
                                  move_event=self._move_event,
                                  timeout=self._timeout)
