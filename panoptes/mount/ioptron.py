from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.set_log_level('debug')
@logger.has_logger
class Mount(AbstractMount):

    """
    iOptron mounts
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initialize_mount(self):
        """
            iOptron init procedure:
                    - Version
                    - MountInfo
        """
        self.logger.info('Initializing {} mount'.format(__name__))
        if not self.is_connected:
        	self.connect()

        if not self.is_initialized:

            # We trick the mount into thinking it's initialized while we initialize
            self.is_initialized = True

            actual_version = self.serial_query('version')
            actual_mount_info = self.serial_query('mount_info')

            expected_version = self.commands.get('version').get('response')
            expected_mount_info = self.commands.get('mount_info').get('response')
            self.is_initialized = False

            # Test our init procedure for iOptron
            if actual_version != expected_version or actual_mount_info != expected_mount_info:
                self.logger.debug('{} != {}'.format(actual_version, expected_version))
                self.logger.debug('{} != {}'.format(actual_mount_info, expected_mount_info))
                raise error.MountNotFound('Problem initializing mount')
            else:
                self.is_initialized = True


        self.serial_query('set_guide_rate', params='050')

        self.logger.debug('Mount initialized: {}'.format(self.is_initialized ))
        return self.is_initialized