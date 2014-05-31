from nose.tools import raises

import panoptes
from panoptes.mount.ioptron import Mount

class TestIOptron():

	@raises(AssertionError)
	def test_no_config_no_commands(self):
		""" Mount needs a config """
		mount = Mount()

	@raises(AssertionError)
	def test_config_bad_commands(self):
		""" Passes in a default config but blank commands, which should error """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } }, commands={'foo': 'bar'})

	def test_config_auto_commands(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } })

	def test_default_settings(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } })
		assert mount.is_connected is False
		assert mount.is_initialized is False
		assert mount.is_slewing is False