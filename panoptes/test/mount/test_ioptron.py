from nose.tools import raises

import panoptes
from panoptes.mount.ioptron import Mount

class TestIOptron():

	@raises(AssertionError)
	def test_no_config_no_commands(self):
		""" Mount needs a config """
		mount = Mount()

	@raises(AssertionError)
	def test_config_no_commands(self):
		""" """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } }, commands=dict())