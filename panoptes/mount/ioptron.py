from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger


@logger.has_logger
class Mount(AbstractMount):

	"""
	iOptron mounts
	"""

	def __init__(self):
		super().__init__()
		self._pre_cmd = ':'

	def setup_commands(self):
		pass
		
	def initialize_mount(self):
	    """ 
	    	iOptron init procedure:
	    		- Version
	    		- MountInfo
	    """
	    if not self.is_initialized:
	    	version = self.serial_query('version')
	    	mount_info = self.serial_query('mount_info')

	    	if version == 'V1.00#' and mount_info == '8407':
	    		self.is_initialized = True

	    return self.is_initialized

	def check_coordinates(self):
		pass

	def sync_coordinates(self):
		pass

	def check_slewing(self):
		# First send the command to get slewing statusonM
		return self.serial_query(self.get_command('slewing'))

	def slew_to_coordinates(self):
		pass

	def slew_to_park(self):
		pass

	def echo(self):
		pass