import threading
from collections import abc
from abc import ABCMeta
from abc import abstractmethod
from contextlib import suppress

from astropy import units as u
from panoptes.pocs.base import PanBase
from panoptes.utils import error
from panoptes.utils.utils import listify


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
        dark_position (int or str, optional): used to specify either a filter wheel position or
            a filter name that should be used when taking dark exposures with a camera that is
            not able to take internal darks.
        focus_offsets (abc.Mapping, optional): Dictionary of filter_name: focus offset pairs to
            apply when moving between filters. If None (default), no offsets are applied.
    """

    def __init__(self,
                 name='Generic Filter Wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 timeout=None,
                 serial_number='XXXXXX',
                 dark_position=None,
                 focus_offsets=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define the focus offsets
        self.focus_offsets = {} if focus_offsets is None else focus_offsets
        if not isinstance(self.focus_offsets, abc.Mapping):
            raise TypeError(f"focus_offsets should be a mapping, got {type(focus_offsets)}.")

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
        try:
            self._timeout = timeout.to_value(unit=u.second)
        except AttributeError:
            self._timeout = timeout
        self._serial_number = serial_number
        if dark_position is not None:
            # Will raise ValueError is dark_position is not a valid position for this filterwheel
            self._dark_position = self._parse_position(dark_position)
        else:
            self._dark_position = None

        self._last_light_position = None
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
        if self._camera and self._camera.uid != camera.uid:
            self.logger.warning(f"{self} assigned to {self.camera.name}, "
                                f"skipping attempted assignment to {camera.name}!")
        elif self._camera:
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
            filter_name = self.filter_name(self.position)
        except ValueError:
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

    def filter_name(self, position):
        """ Name of the filter in the given integer position. """
        # Validate input by passing it through _parse_position(), may raise ValueError
        int_position = self._parse_position(position)
        return self.filter_names[int_position - 1]

    def move_to(self, new_position, blocking=False):
        """
        Move the filter wheel to the given position.

        The position can be expressed either as an integer, or as (part of) one of the names from
        the filter_names list. To allow filter names of the form '<filter band>_<serial number>'
        to be selected by band only position can be a substring from the start of one
        of the names in the filter_names list, provided that this produces only one match.

        Args:
            new_position (int or str): position to move to.
            blocking (bool, optional): If False (default) return immediately, if True block until
                the filter wheel move has been completed.

        Returns:
            threading.Event: Event that will be set to signal when the move has completed

        Raise:
            ValueError: if new_position is not a valid position specifier for this filterwheel.

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

        if self.is_moving:
            msg = f'Attempt to move filter wheel {self} while already moving, ignoring.'
            self.logger.error(msg)
            raise error.PanError(msg)

        if self.camera is not None:

            if self.camera.is_exposing:
                raise error.PanError(f'Attempt to move filter wheel {self} while camera is'
                                     ' exposing, ignoring.')

            if self.camera.has_focuser:
                try:
                    self._apply_filter_focus_offset(new_position)
                except Exception as err:
                    self.logger.error(f"Unable to apply focus position offset on {self}: {err!r}")

        # Will raise a ValueError at this point if new_position is not a valid position
        new_position = self._parse_position(new_position)

        if new_position == self.position:
            # Already at requested position, don't go nowhere.
            self.logger.debug(f"{self} already at position {new_position}"
                              f" ({self.filter_name(new_position)})")
            return self._move_event

        # Store current position so we can revert back with move_to_light_position()
        if new_position == self._dark_position:
            self._last_light_position = self.position
        else:
            self._last_light_position = new_position

        self.logger.info("Moving {} to position {} ({})".format(
            self, new_position, self.filter_name(new_position)))
        self._move_event.clear()
        self._move_to(new_position)  # Private method to actually perform the move.

        if blocking:
            self._move_event.wait()

        return self._move_event

    def move_to_dark_position(self, blocking=False):
        """ Move to filterwheel position for taking darks. """
        try:
            self.logger.debug(f"Ensuring filterwheel {self} is at dark position.")
            return self.move_to(self._dark_position, blocking=blocking)
        except ValueError:
            msg = f"Request to move to dark position but {self} has no dark_position set."
            raise error.NotFound(msg)

    def move_to_light_position(self, blocking=False):
        """ Return to last filterwheel position from before taking darks. """
        try:
            self.logger.debug(f"Ensuring filterwheel {self} is not at dark position.")
            return self.move_to(self._last_light_position, blocking=blocking)
        except ValueError:
            msg = f"Request to revert to last light position but {self} has" + \
                  "no light position stored."
            raise error.NotFound(msg)

    ##################################################################################################
    # Private methods
    ##################################################################################################

    @abstractmethod
    def _move_to(self, position):
        raise NotImplementedError

    def _parse_position(self, position):
        """
        Converts a requested position to an integer filter wheel position.

        If position is a string it will search the list of filter names for one that begins with
        that string and return the corresponding integer position, otherwise (or if there is no
        match) it will do an explicit cast to an integer.
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
            except (ValueError, TypeError):
                msg = f"No match for '{position}' in filter_names and not an integer either"
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

    def _apply_filter_focus_offset(self, new_position):
        """ Apply the filter-specific focus offset.
        Args:
            new_position (int or str): The new filter name or filter position.
        """
        if self.focus_offsets is None:  # Nothing to do here
            self.logger.debug("Found no filter focus offsets to apply.")
            return

        new_filter = self.filter_name(new_position)
        try:
            new_offset = self.focus_offsets[new_filter]
        except KeyError:
            self.logger.warning(f"No focus offset found for {new_filter} filter.")
            return

        current_offset = self.focus_offsets.get(self.current_filter, 0)
        focus_offset = new_offset - current_offset

        self.logger.debug(f"Applying focus position offset of {focus_offset} moving from filter "
                          f"{self.current_filter} to {new_filter}.")
        self.camera.focuser.move_by(focus_offset)

    def __str__(self):
        s = f'{self.name} ({self.uid})'

        try:
            with suppress(AttributeError):
                s += f' [Camera: {self.camera.name}]'
        except Exception as e:  # noqa
            self.logger.warning(f'Unable to stringify filterwheel: e={e!r}')
            s = str(self.__class__)

        return s
