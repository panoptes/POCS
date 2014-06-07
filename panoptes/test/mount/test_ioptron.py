import nose.tools
from nose.plugins.skip import Skip, SkipTest
from nose.plugins.attrib import attr

import panoptes
from panoptes.mount.ioptron import Mount
import panoptes.utils.error as error

import ephem

class TestIOptron():

    def __init__(self):     
        self.good_config = {'model': 'ioptron', 'port': '/dev/ttyUSB0'}

        self.site = ephem.Observer()
        self.site.lon = '-155:34:34.3164'
        self.site.lat = '19:32:09.3876'

    def connect_with_skip(self):
        """
        This is a convenience function which attempts to connect and raises SkipTest if cannot
        """
        mount = Mount(config=self.good_config)
        try:
            mount.connect()
        except:
            raise SkipTest('No serial connection to mount')

        return mount

    def connect_with_site(self):
        """
        This is a convenience function which attempts to connect and raises SkipTest if cannot
        and also sets the site from the config
        """
        site = ephem.Observer()
        mount = Mount(config=self.good_config, site=site)
        try:
            mount.connect()
        except:
            raise SkipTest('No serial connection to mount')

        return mount

    # BEGIN TESTS BELOW ##################################

    @attr('stable')
    @nose.tools.raises(AssertionError)
    def test_000_no_config_no_commands(self):
        """ Mount needs a config """
        mount = Mount()

    @attr('stable')
    @nose.tools.raises(AssertionError)
    def test_001_config_bad_commands(self):
        """ Passes in a default config but blank commands, which should error """
        mount = Mount(config=self.good_config, commands={'foo': 'bar'})

    @attr('stable')
    def test_002_config_auto_commands(self):
        """ Passes in config like above, but no commands, so they should read from defaults """
        mount = Mount(config=self.good_config)

    @attr('stable')
    def test_003_default_settings(self):
        """ Passes in config like above, but no commands, so they should read from defaults """
        mount = Mount(config=self.good_config)
        assert mount.is_connected is False
        assert mount.is_initialized is False

    @attr('stable')
    def test_004_port_set(self):
        """ Passes in config like above, but no commands, so they should read from defaults """
        mount = Mount(config=self.good_config)
        nose.tools.eq_(mount.port, '/dev/ttyUSB0')

    @attr('stable')
    @nose.tools.raises(error.BadSerialConnection)
    def test_005_connect_broken(self):
        """ Test connecting to the mount after setup """
        mount = Mount(config={'model': 'ioptron', 'port': '/dev/fooBar'})
        mount.connect()

    @attr('stable')
    def test_006_connect(self):
        """ Test connecting to the mount after setup. If we are not connected, we skip tests """
        mount = self.connect_with_skip()

        assert mount.is_connected

    @attr('stable')
    def test_007_initialize_mount(self):
        """ Test the mounts initialization procedure """
        mount = self.connect_with_skip()
        mount.initialize_mount()

        assert mount.is_initialized

    @attr('stable')
    @nose.tools.raises(error.InvalidMountCommand)
    def test_008_bad_command(self):
        """ Give a bad command to the telescope """
        mount = self.connect_with_skip()

        mount._get_command('foobar')

    @attr('stable')
    def test_009_version_command(self):
        """ Tests the 'version' command as an example of a basic command """
        mount = self.connect_with_skip()

        correct_cmd = ':V#'

        cmd = mount._get_command('version')

        nose.tools.eq_(correct_cmd, cmd,
                       'Received command does not match expected')

    @attr('stable')
    @nose.tools.raises(NotImplementedError)
    def test_010_echo(self):
        """
        Test an echo command

        """
        mount = self.connect_with_skip()
        mount.echo()

    @attr('stable')
    def test_011_query_version(self):
        """
        Query the mount for the version
        """
        mount = self.connect_with_skip()
        mount.initialize_mount()

        version = mount.serial_query('version')

        expected_version = mount.commands.get('version').get('response')

        # Test our init procedure for iOptron
        nose.tools.eq_(version, expected_version)

    @attr('stable')
    @nose.tools.raises(error.InvalidMountCommand)
    def test_012_query_without_params(self):
        """
        Try to send a command that requires params without params
        """
        mount = self.connect_with_skip()
        mount.initialize_mount()
        
        mount.serial_query('set_local_date')

    @attr('stable')
    def test_013_set_date(self):
        """
        Where the mount reports itself at start
        """
        mount = self.connect_with_skip()
        mount.initialize_mount()

        dt1 = '12:25:13'

        # First we set the date incorrectly
        mount.serial_query('set_local_date', dt1)

        # Then check what we got
        dt2 = mount.serial_query('get_local_date')

        # Check date is okay
        nose.tools.eq_(dt1, dt2)

        # Reset to today
        import datetime as dt
        now = dt.datetime.now()
        today = '{:02d}:{:02d}:{:02d}'.format(now.month, now.day, now.year-2000)
        
        mount.serial_query('set_local_date', today)

    def test_014_setup_site(self):
        """
        Set up the mount using a site
        """
        mount = self.connect_with_skip()
        mount.initialize_mount()
        mount.setup_site(self.site)

        nose.tools.eq_(str(self.site.lon), mount.serial_query('get_long'))
        nose.tools.eq_(str(self.site.lat), mount.serial_query('get_lat'))
