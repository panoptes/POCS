from panoptes.mount.mount import AbstractMount

from ..utils.logger import has_logger
from ..utils.config import load_config


@has_logger
class Mount(AbstractMount):

    """Mount class for a simulator. Use this when you don't actually have a mount attached.
    """

    def __init__(self,
                 config=dict(),
                 commands=dict(),
                 location=None,
                 *args, **kwargs
                 ):
        self.logger.info('Creating simulator mount')
        kwargs.setdefault('simulator', True)
        super().__init__(*args, **kwargs)

        self.config = load_config()

        self.logger.info('Simulator mount created')


##################################################################################################
# Properties
##################################################################################################

    @property
    def is_parked(self):
        """ bool: Mount parked status. """
        self._is_parked = 'Parked' in self.status().get('system', '')

        return self._is_parked

    @property
    def is_home(self):
        """ bool: Mount home status. """
        self._is_home = 'Stopped - Zero Position' in self.status().get('system', '')

        return self._is_home

    @property
    def is_tracking(self):
        """ bool: Mount tracking status. """
        self._is_tracking = 'Tracking' in self.status().get('system', '')

        return self._is_tracking

    @property
    def is_slewing(self):
        """ bool: Mount slewing status. """
        self._is_slewing = 'Slewing' in self.status().get('system', '')

        return self._is_slewing


##################################################################################################
# Public Methods
##################################################################################################

    def initialize(self):
        """ Initialize the connection with the mount and setup for location.

        iOptron mounts are initialized by sending the following two commands
        to the mount:

        * Version
        * MountInfo

        If the mount is successfully initialized, the `_setup_location_for_mount` method
        is also called.

        Returns:
            bool:   Returns the value from `self.is_initialized`.
        """
        self.is_ininitialized = True

        return self.is_initialized

    def connect(self):
        self.logger.info("Connecting to mount.")
        self._is_connected = True
        return True

##################################################################################################
# Private Methods
##################################################################################################

    def _setup_location_for_mount(self):
        """Sets the mount up to the current location. Mount must be initialized first. """
        assert self.is_initialized, self.logger.warning('Mount has not been initialized')
        assert self.location is not None, self.logger.warning('Please set a location before attempting setup')

        self.logger.info('Setting up mount for location')

    def _mount_coord_to_skycoord(self, mount_coords):
        """ Returns same coords """
        return mount_coords

    def _skycoord_to_mount_coord(self, coords):
        """ Returns same coords """

        return coords

    def _set_zero_position(self):
        """ Sets the current position as the zero position. """
        self.logger.info("Simulator cannot set zero position")
        return False

    def _setup_commands(self, commands):
        return commands
