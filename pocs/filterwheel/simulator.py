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
        timeout (u.Quantity, optional): maximum time to wait for a move to complete. Should be
            a Quantity with time units. If a numeric type without units is given seconds will be
            assumed. Default is 10 seconds.
        serial_number (str): serial number of the filter wheel
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
                 timeout=10 * u.second,
                 serial_number=None,
                 move_time=1 * u.second,
                 move_bidirectional=False,
                 *args, **kwargs):
        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_names,
                         timeout=timeout,
                         serial_number=serial_number,
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
        self._serial_number = 'SW{:04d}'.format(random.randint(0, 9999))
        self._position = 1
        self._moving = False
        self.logger.info("Filter wheel {} initialised".format(self))
        self._connected = True

##################################################################################################
# Private methods
##################################################################################################

    def _move_to(self, position, move_event):
        if self._moving:
            move_event.set()
            msg = "Attempt to move filter wheel when already moving"
            self.logger.error(msg)
            raise RuntimeError(msg)

        move_distance = position - self.position
        if self._move_birectional:
            # Filter wheel can move either direction, just need magnitude of the move.
            move_distance = abs(move_distance)
        else:
            # Filter wheel can only move one way, will have to go the long way around for -ve moves
            move_distance = move_distance % self._n_positions
        move_duration = move_distance * self._move_time

        move = threading.Timer(interval=move_duration,
                               function=self._complete_move,
                               args=(position, move_event))
        self._position = float('nan')
        self._moving = True
        move.start()

        if move_duration > self._timeout:
            timeout_timer = threading.Timer(interval=self._timeout,
                                            function=self._timeout_move,
                                            args=(move_event,))
            timeout_timer.start()

    def _complete_move(self, position, move_event):
        self._moving = False
        self._position = position
        move_event.set()

    def _timeout_move(self, move_event):
        move_event.set()
        msg = "Timeout waiting for filter wheel move to complete"
        raise error.Timeout(msg)
