"""SBIG filter wheel integration via the SBIG camera SDK.

Provides a FilterWheel implementation that controls SBIG wheels attached to an
SBIG camera (via I2C) using the existing SBIG camera driver.
"""

import math

from astropy import units as u

from panoptes.pocs.camera.sbig import Camera as SBIGCamera
from panoptes.pocs.filterwheel import AbstractFilterWheel


class FilterWheel(AbstractFilterWheel):
    """
    Class for SBIG filter wheels connected to the I2C port of an SBIG camera.

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.sbig.Camera): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
        timeout (u.Quantity, optional): maximum time to wait for a move to complete. Should be
            a Quantity with time units. If a numeric type without units is given seconds will be
            assumed. Default is 10 seconds.
        serial_number (str): serial number of the filter wheel
    """

    def __init__(
        self,
        name="SBIG Filter Wheel",
        model="sbig",
        camera=None,
        filter_names=None,
        timeout=10 * u.second,
        serial_number=None,
        *args,
        **kwargs,
    ):
        if camera is None:
            msg = "Camera must be provided for SBIG filter wheels"
            self.logger.error(msg)
            raise ValueError(msg)
        if not isinstance(camera, SBIGCamera):
            msg = f"Camera must be an instance of pocs.camera.sbig.Camera, got {camera}"
            self.logger.error(msg)
            raise ValueError(msg)
        super().__init__(
            name=name,
            model=model,
            camera=camera,
            filter_names=filter_names,
            timeout=timeout,
            serial_number=serial_number,
            *args,
            **kwargs,
        )

    ##################################################################################################
    # Properties
    ##################################################################################################

    @property
    def firmware_version(self):
        """Firmware version of the filter wheel"""
        return self._firmware_version

    @AbstractFilterWheel.position.getter
    def position(self):
        """Current integer position of the filter wheel"""
        status = self._driver.cfw_query(self._handle)
        if math.isnan(status["position"]):
            self.logger.warning("Filter wheel position unknown, returning NaN")
        return status["position"]

    @property
    def is_moving(self):
        """Is the filterwheel currently moving"""
        status = self._driver.cfw_query(self._handle)
        if status["status"] == "UNKNOWN":
            self.logger.warning(f"{self} returned 'UNKNOWN' status")
        return bool(status["status"] == "BUSY")

    @property
    def is_unidirectional(self):
        """Whether the wheel enforces one-way rotation.

        Returns:
            bool: Always True for SBIG filter wheels.
        """
        # All SBIG filterwheels unidirectional?
        return True

    ##################################################################################################
    # Methods
    ##################################################################################################

    def connect(self):
        """
        Connect to filter wheel. Not called by __init__ because we need the camera to be connected
        first. The SBIG camera connect() method will call this once it's OK to do so.
        """
        assert self.camera.is_connected, self.logger.error(
            f"Can't connect {self}, camera not connected"
        )
        self._driver = self.camera._driver
        self._handle = self.camera._handle

        info = self._driver.cfw_get_info(self._handle)
        self._model = info["model"]
        self._firmware_version = info["firmware_version"]
        self._n_positions = info["n_positions"]
        if len(self.filter_names) != self.n_positions:
            msg = (
                f"Number of names in filter_names ({len(self.filter_names)}) doesn't"
                + f" match number of positions in filter wheel ({self.n_positions})"
            )
            self.logger.error(msg)
            raise ValueError(msg)

        self.logger.info(f"Filter wheel {self} initialised")
        self._connected = True

    def recalibrate(self):
        """
        Reinitialises/recalibrates the filter wheel. It should not be necessary to call this as
        SBIG filter wheels initialise and calibrate themselves on power up.
        """
        self._driver.cfw_init(handle=self._handle, timeout=self._timeout)
        self.logger.info(f"{self} recalibrated")

    ##################################################################################################
    # Private methods
    ##################################################################################################

    def _move_to(self, position):
        self._driver.cfw_goto(
            handle=self._handle,
            position=position,
            cfw_event=self._move_event,
            timeout=self._timeout,
        )

    def _add_fits_keywords(self, header):
        header = super()._add_fits_keywords(header)
        header.set("FW-FW", self.firmware_version, "Filter wheel firmware version")
        return header
