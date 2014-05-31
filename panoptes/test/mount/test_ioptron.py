import nose.tools

import panoptes
from panoptes.mount.ioptron import Mount
import panoptes.utils.error as error

class TestIOptron():

	@nose.tools.raises(AssertionError)
	def test_no_config_no_commands(self):
		""" Mount needs a config """
		mount = Mount()

	@nose.tools.raises(AssertionError)
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

	def test_port_set(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } })
		nose.tools.eq_(mount.port, '/dev/ttyUSB0')

	@nose.tools.raises(AssertionError)
	def test_connect_broken(self):
		""" Test connecting to the mount after setup """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } })
		mount.connect()

	@nose.tools.raises(error.InvalidMountCommand)
	def test_bad_command(self):
		""" Test connecting to the mount after setup """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' } })
		mount.get_command('foobar')
