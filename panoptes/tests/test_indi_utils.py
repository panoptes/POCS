import os
import pytest

from ..utils.indi import PanIndiServer, PanIndiDevice
from ..utils.logger import get_logger

logger = get_logger(self)


class TestIndiBasics(object):

    """ Class for testing INDI modules """

    def test_server_create_and_delete(self):
        """ Creates a server with no config, test it is there, delete it and make sure gone. """
        logger.info("Running test_server_create_and_delete")

        indi_server = PanIndiServer()
        pid = indi_server._proc.pid
        fifo_file = indi_server._fifo

        assert pid > 0, "No PID found"
        assert os.getpgid(pid), "OS Can't find PID"
        assert indi_server.is_connected, "Server not connected"

        del indi_server
        assert os.getpgid(pid) is not True, "Server still running, didn't shut down properly"
        assert os.path.exists(fifo_file) is not True, "FIFO still exists"

    def test_device_create(self):
        """ Create a device, no server """
        logger.info("Running test_device_create")

        device = None
        with pytest.raises(TypeError):
            device = PanIndiDevice()

        name = 'TestDevice'
        driver = 'indi_simulator_ccd'

        device = PanIndiDevice(name, driver)
        assert isinstance(device, PanIndiDevice), "Didn't return a device"

        assert device.is_loaded is not True, "Device driver not loaded"
        assert device.is_connected is not True, "Device not connected"

    def test_basic(self):
        """ Create a server and a device. Connect device """

        logger.info("Running test_basic")

        indi_server = PanIndiServer()

        assert indi_server.is_connected, "Server not connected"

        name = 'TestDevice'
        driver = 'indi_simulator_ccd'
        device = PanIndiDevice(name, driver)

        indi_server.load_driver(name, driver)

        assert device.is_loaded, "Device driver not loaded"
        del indi_server

    def test_v4l2(self):
        """ Create a server and a device. Connect webcam device and take a picture """

        logger.info("Running test_v4l2")

        indi_server = PanIndiServer()

        assert indi_server.is_connected, "Server not connected"

        name = 'TestWebCam'
        driver = 'indi_v4l2_ccd'
        device = PanIndiDevice(name, driver)

        indi_server.load_driver(name, driver)

        device.connect()

        assert device.is_connected, "WebCam is not on"

        assert device.is_loaded, "Device driver not loaded"
