from panoptes import mount

class TestMount: 

    mount = None

    def setup(self):
        print ("TestMount:setup() before each test method")
 
    def teardown(self):
        print ("TestMount:teardown() after each test method")
 
    @classmethod
    def setup_class(cls):
        print ("setup_class() before any methods in this class")
        cls.mount = mount.Mount()
 
    @classmethod
    def teardown_class(cls):
        print ("teardown_class() after any methods in this class")

    def test_is_connected_false(self):
        pass

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
