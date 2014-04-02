import os
import importlib
import warnings

class TestMounts: 

    _MountModules = []
    _Mounts = []

    def setup(self):
        print ("TestMount:setup() before each test method")
 
    def teardown(self):
        print ("TestMount:teardown() after each test method")
 
    @classmethod
    def setup_class(cls):
        mount_dir = os.path.dirname(__file__) + '/../mount/'
        print ("setup_class() before any methods in this class")
        for name in os.listdir(os.path.dirname(mount_dir)):
            if not name.startswith('_') and name.endswith('.py'):
                name = '.' + os.path.splitext(name)[0]
                try:
                    module = importlib.import_module(name,'panoptes.mount')
                    if hasattr(module, 'Mount'):
                        cls._MountModules.append(module)
                        cls._Mounts.append(module.Mount())
                except ImportError as err:
                    warnings.warn('Failed to load mount plugin: {}'.format(err))
 
    @classmethod
    def teardown_class(cls):
        print ("teardown_class() after any methods in this class")

    def test_is_connected_false(self):
        for mount in self._Mounts:
            assert not mount.is_connected, "Mount is not connected"

    def test_connect(self):
        pass

    def test_is_connected_true(self):
        pass

    def test_is_slewing(self):
        pass

    def test_check_coordinates(self):
        pass

    def test_sync_coordinates(self):
        pass

    def test_slew_to_coordinates(self):
        pass

    def test_slew_to_park(self):
        pass

    def test_echo(self):
        pass
