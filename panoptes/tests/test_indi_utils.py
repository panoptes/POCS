import os, sys
import pytest
import astropy.units as u


from ..utils import load_config, has_logger, error
from ..utils.indi import PanIndiServer, PanIndiDevice

class TestIndi(object):
    """ Class for testing INDI modules """

    def test_server_create_and_delete(self):
        """ Creates a server with no config, test it is there, delete it and make sure gone. """

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
        """ Create a device """

        device = None
        with pytest.raises(TypeError):
            device = PanIndiDevice()

        name = 'TestDevice'
        driver = 'indi_simulator_ccd'
        device = PanIndiDevice(name, driver)
        assert isinstance(device, PanIndiDevice), "Didn't return a device"

        with pytest.raises(error.InvalidCommand):
            assert device.is_connected is not True, "Device not connected"
