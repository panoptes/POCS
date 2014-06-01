import nose.tools
from nose.plugins.skip import Skip, SkipTest

import panoptes
from panoptes.mount.ioptron import Mount
import panoptes.utils.error as error

class TestIOptron():

	
	good_config = {'mount': { 'model': 'ioptron', 'port':'/dev/ttyUSB0' }}

	def connect_with_skip(self, mount):
		"""
		This is a convenience function which attempts to connect and raises SkipTest if cannot
		"""
		try:
			mount.connect()
		except:
			raise SkipTest


	############################# BEGIN TESTS BELOW ##################################

	@nose.tools.raises(AssertionError)
	def test_no_config_no_commands(self):
		""" Mount needs a config """
		mount = Mount()

	@nose.tools.raises(AssertionError)
	def test_config_bad_commands(self):
		""" Passes in a default config but blank commands, which should error """
		mount = Mount(config=self.good_config, commands={'foo': 'bar'})

	def test_config_auto_commands(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config=self.good_config)

	def test_default_settings(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config=self.good_config)
		assert mount.is_connected is False
		assert mount.is_initialized is False
		assert mount.is_slewing is False

	def test_port_set(self):
		""" Passes in config like above, but no commands, so they should read from defaults """
		mount = Mount(config=self.good_config)
		nose.tools.eq_(mount.port, '/dev/ttyUSB0')

	@nose.tools.raises(error.BadSerialConnection)
	def test_connect_broken(self):
		""" Test connecting to the mount after setup """
		mount = Mount(config={'mount': { 'model': 'ioptron', 'port':'/dev/fooBar' } })
		mount.connect()

	def test_connect(self):
		""" Test connecting to the mount after setup. If we are not connected, we skip tests """
		mount = Mount(config=self.good_config)
		self.connect_with_skip(mount)

		assert mount.is_connected

	def test_initialize_mount(self):
		""" Test the mounts initialization procedure """
		mount = Mount(config=self.good_config)
		self.connect_with_skip(mount)

		assert mount.is_initialized

	@nose.tools.raises(error.InvalidMountCommand)
	def test_bad_command(self):
		""" Give a bad command to the telescope """
		mount = Mount(config=self.good_config)
		self.connect_with_skip(mount)

		mount.get_command('foobar')

	def test_version_command(self):
		""" Tests the 'version' command as an example of a basic command """
		mount = Mount(config=self.good_config)
		self.connect_with_skip(mount)

		mount.get_command('version')
