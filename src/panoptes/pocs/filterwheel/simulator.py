import math
import random
import threading

from astropy import units as u

from panoptes.utils import error
from panoptes.pocs.filterwheel import AbstractFilterWheel


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
        move_time (astropy.units.Quantity, optional): time to move the filter wheel by one
            position, optional, default 1 second.
        unidirectional (bool, optional): If True filterwheel will only rotate in one direction, if
            False filterwheel will move in either to get to the requested position via the
            shortest path. Default is True.
    """

    def __init__(self,
                 name='Simulated Filter Wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 timeout=10 * u.second,
                 serial_number=None,
                 move_time=1 * u.second,
                 unidirectional=True,
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
        self._unidirectional = bool(unidirectional)
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

    @property
    def is_moving(self):
        """ Is the filterwheel currently moving """
        return self._moving

    @property
    def is_unidirectional(self):
        return self._unidirectional

##################################################################################################
# Methods
##################################################################################################

    def connect(self):
        """ Connect to the filter wheel """
        self._serial_number = 'SW{:04d}'.format(random.randint(0, 9999))
        self._position = 1
        self._moving = False
        self._connected = True

##################################################################################################
# Private methods
##################################################################################################

    def _move_to(self, position):
        if self._moving:
            self._move_event.set()
            msg = "Attempt to move filter wheel when already moving"
            self.logger.error(msg)
            raise RuntimeError(msg)

        move_distance = position - self.position
        if self.is_unidirectional:
            # Filter wheel can only move one way, will have to go the long way around for -ve moves
            move_distance = move_distance % self._n_positions
        else:
            # Filter wheel can move either direction, just need magnitude of the move.
            move_distance = abs(move_distance)
        move_duration = move_distance * self._move_time

        move = threading.Timer(interval=move_duration,
                               function=self._complete_move,
                               args=(position,))
        self._position = float('nan')
        self._moving = True
        move.start()

        if move_duration > self._timeout:
            move.join(timeout=self._timeout)
            # If still alive then kill and raise timeout
            if move.is_alive():
                self._move_event.set()
                self._moving = False
                msg = "Timeout waiting for filter wheel move to complete"
                self.logger.error(msg)
                raise error.Timeout(msg)

    def _complete_move(self, position):
        self._moving = False
        self._position = position
        self._move_event.set()

    def _timeout_move(self):
        self._move_event.set()
        msg = "Timeout waiting for filter wheel move to complete"
        self.logger.error(msg)
        raise error.Timeout(msg)
