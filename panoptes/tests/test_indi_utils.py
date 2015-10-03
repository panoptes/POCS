import os, sys
import pytest
import astropy.units as u


from ..utils import load_config, has_logger
from ..utils.indi import PanIndiServer, PanIndiDevice

class TestIndi(object):
    """ Class for testing INDI modules """

    def test_create_and_delete(self):
        """ Creates a server with no config, test it is there, delete it and make sure gone. """

        indi_server = PanIndiServer()
        pid = indi_server._proc.pid
        fifo_file = indi_server._fifo
        
        assert pid > 0, "No PID found"
        assert os.getpgid(pid), "OS Can't find PID"

        del indi_server
        assert os.getpgid(pid) is not True, "Server still running, didn't shut down properly"
        assert os.path.exists(fifo_file) is not True, "FIFO still exists"
