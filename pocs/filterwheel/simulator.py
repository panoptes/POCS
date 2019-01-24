import math
import time
import random
import threading

from astropy import units as u

from pocs.utils import error
from pocs.filterwheel import AbstractFilterWheel


class FilterWheel(AbstractFilterWheel):
    """
    Class for simulated filter wheels.

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.*.Camera, optional): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
        move_time (astropy.units.Quantity, optional): time to move the filter wheel by one position,
            optional, default 1 second.
        move_bidirectional (bool, optional): if True will simulate filter wheel which can rotate in
            either direction, if False (default) will similate a filter wheel that only moves in
            one direction.
    """
    def __init__(self,
                 name='Simulated Filter Wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 move_time=1 * u.second,
                 move_bidirectional=False,
                 *args, **kwargs):
        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_names,
                         *args, **kwargs)
        if isinstance(move_time, u.Quantity):
            self._move_time = move_time.to(u.second).value
        else:
            self._move_time = move_time
        self._move_birectional = bool(move_bidirectional)
        self.connect()
        self.logger.info("Filter wheel {} initialised".format(self))

##################################################################################################
# Properties
##################################################################################################

    @AbstractFilterWheel.position.getter
    def position(self):
        """ Current integer position of the filter wheel """
        if math.isnan(self._position):
            self.logger.warning("Filter wheel position unknown, returning NaN")
        return self._position

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connect to the filter wheel """
        self._serial_number = 'SF{:04d}'.format(random.randint(0, 9999))
        self._position = 1
        self._moving = False
        self._connected = True

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
        if isinstance(timeout, u.Quantity):
                timeout = timeout.to(u.second).value

        move_event = threading.Event()
        if self._moving:
            move_event.set()
            msg = "Attempt to move filter wheel when already moving"
            self.logger.error(msg)
            raise RuntimeError(msg)

        move_distance = position - self.position
        if move_distance < 0:
            if not self._move_birectional:
                move_distance += self._n_positions
            else:
                move_distance = -move_distance
        move_duration = move_distance * self._move_time

        move = threading.Timer(interval=move_duration,
                               function=self._complete_move,
                               args=(position, move_event))
        self._moving = True
        self._position = float('nan')
        move.start()

        if move_duration > timeout:
            timeout_timer = threading.Timer(interval=timeout,
                                            function=self._timeout_move,
                                            args=(move_event))
            timeout_timer.start()

        if blocking:
            move_event.wait()

        return move_event

##################################################################################################
# Private methods
##################################################################################################

    def _complete_move(self, position, move_event):
        self._position = position
        self._moving = False
        move_event.set()

    def _timeout_move(self, move_event):
        move_event.set()
        msg = "Timeout waiting for filter wheel move to complete"
        raise error.Timeout(msg)
