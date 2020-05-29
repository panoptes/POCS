import threading
from abc import ABCMeta, abstractmethod

from astropy import units as u

from panoptes.pocs.base import PanBase
from panoptes.utils import listify
from panoptes.utils import error


class AbstractFilterWheel(PanBase, metaclass=ABCMeta):
    """
    Base class for all filter wheels

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.*.Camera, optional): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
        timeout (u.Quantity, optional): maximum time to wait for a move to complete. Should be
            a Quantity with time units. If a numeric type without units is given seconds will be
            assumed. Default is None (no timeout).
        serial_number (str, optional): serial number of the filter wheel, default 'XXXXXX'
    """

    def __init__(self,
                 name='Generic Filter Wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 timeout=None,
                 serial_number='XXXXXX',
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._model = model
        self._name = name
        self._camera = camera
        self._filter_names = [str(name) for name in listify(filter_names)]
        if not self._filter_names:
            # Empty list
            msg = "Must provide list of filter names"
            self.logger.error(msg)
            raise ValueError(msg)
        self._n_positions = len(filter_names)
        if isinstance(timeout, u.Quantity):
            self._timeout = timeout.to(u.second).value
        else:
            self._timeout = timeout
        self._serial_number = serial_number
        self._connected = False

        # Some filter wheels needs this to track whether they are moving or not.
        self._move_event = threading.Event()
        self._move_event.set()

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
    @abstractmethod
    def is_moving(self):
        """ Is the filterwheel currently moving """
        raise NotImplementedError

    @property
    def is_ready(self):
        # A filterwheel is 'ready' if it is connected and isn't currently moving.
        return self.is_connected and not self.is_moving

    @property
    def camera(self):
        """
        Reference to the Camera object that the FilterWheel is assigned to, if any. A filter wheel
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

    @property
    @abstractmethod
    def position(self):
        """ Current integer position of the filter wheel """
        raise NotImplementedError

    @position.setter
    def position(self, position):
        self.move_to(position, blocking=True)

    @property
    def current_filter(self):
        """ Name of the filter in the current position """
        try:
            filter_name = self.filter_names[self.position - 1]  # 1 based numbering
        except (IndexError, TypeError):
            # Some filter wheels sometimes cannot return their current position
            filter_name = "UNKNOWN"
        return filter_name

    @current_filter.setter
    def current_filter(self, filter_name):
        self.move_to(filter_name, blocking=True)

    @property
    def is_unidirectional(self):
        raise NotImplementedError

##################################################################################################
# Methods
##################################################################################################

    @abstractmethod
    def connect(self):
        """ Connect to filter wheel """
        raise NotImplementedError

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

        Examples:
            Substring matching is useful when the filter names contain both the type of filter
            and a serial number, e.g. the following selects a g band filter without having to
            know its full name.

            >>> from panoptes.pocs.filterwheel.simulator import FilterWheel
            >>> fw = FilterWheel(filter_names=['u_12', 'g_04', 'r_09', 'i_20', 'z_07'])
            >>> fw_event = fw.move_to('g')
            >>> fw_event.wait()
            True
            >>> fw.current_filter
            'g_04'
        """
        assert self.is_connected, self.logger.error("Filter wheel must be connected to move")

        if self.camera and self.camera.is_exposing:
            msg = f'Attempt to move filter wheel {self} while camera is exposing, ignoring.'
            self.logger.error(msg)
            raise error.PanError(msg)

        if self.is_moving:
            msg = f'Attempt to move filter wheel {self} while already moving, ignoring.'
            self.logger.error(msg)
            raise error.PanError(msg)

        position = self._parse_position(position)
        self.logger.info("Moving {} to position {} ({})".format(
            self, position, self.filter_names[position - 1]))

        if position == self.position:
            # Already at requested position, don't go nowhere.
            return self._move_event

        self._move_event.clear()
        self._move_to(position)  # Private method to actually perform the move.

        if blocking:
            self._move_event.wait()

        return self._move_event

##################################################################################################
# Private methods
##################################################################################################

    @abstractmethod
    def _move_to(self, position, move_event):
        raise NotImplementedError

    def _parse_position(self, position):
        """
        Converts a requested position to an integer filter wheel position.

        If position is a string it will search the list of filter names for one that begins with
        that string and return the corresponding integer position, otherwise (or if there is no
        match) it will do an explicity case to an integer.
        """
        int_position = None
        if isinstance(position, str):
            # Got a string, so search for a match in the filter names list
            for i, filter_name in enumerate(self.filter_names):
                if filter_name.startswith(position):
                    if int_position is None:
                        int_position = i + 1  # 1 based numbering for filter wheel positions
                    else:
                        # Already matched at least once
                        msg = "More than one filter name matches '{}', using '{}'".format(
                            position, self.filter_names[int_position - 1])
                        self.logger.warning(msg)
                        break

        if int_position is None:
            # Not a string or no match. Try to use as an integer position number.
            try:
                int_position = int(position)
            except ValueError:
                msg = "No match for '{}' in filter_names, & not an integer either".format(position)
                self.logger.error(msg)
                raise ValueError(msg)

        if int_position < 1 or int_position > self.n_positions:
            msg = f'Position must be between 1 and {self.n_positions}, got {int_position}'
            self.logger.error(msg)
            raise ValueError(msg)

        return int_position

    def _add_fits_keywords(self, header):
        header.set('FW-NAME', self.name, 'Filter wheel name')
        header.set('FW-MOD', self.model, 'Filter wheel model')
        header.set('FW-ID', self.uid, 'Filter wheel serial number')
        header.set('FW-POS', self.position, 'Filter wheel position')
        return header

    def __str__(self):
        try:
            if self.camera:
                s = "{} ({}) on {}".format(self.name, self.uid, self.camera.uid)
            else:
                s = "{} ({})".format(self.name, self.uid)
        except Exception:
            s = str(self.__class__)

        return s
