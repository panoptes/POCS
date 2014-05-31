from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger

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
            actual_version = self.serial_query('version')
            actual_mount_info = self.serial_query('mount_info')

            expected_version = self.commands.get('version').get('response')
            expected_mount_info = self.commands.get('mount_info').get('response')

            # Test our init procedure for iOptron
            if actual_version != expected_version or actual_mount_info != expected_mount_info:
                raise MountNotFound('Problem initializing mount')
            else:
                self.is_initialized = True

        self.logger.debug('Mount initialized: {}'.format(self.is_initialized ))
        return self.is_initialized