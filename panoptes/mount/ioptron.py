from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger


@logger.has_logger
class Mount(AbstractMount):

	"""
	iOptron mounts
	"""

	def __init__(self):
		super().__init__()

	def setup_commands(self):
		return {
                    'slewing': ':SE?#',
                    'version': ':V#',
                    'mount_info': ':MountInfo#'
		}

	def initialize_mount(self):
	    """ 
	    	iOptron init procedure:
	    		- Version
	    		- MountInfo
	    """
	    if not self.is_initialized:
	    	version = self.send_command('version')
	    	mount_info = self.send_command('mount_info')

	    	if version == 'V1.00#' and mount_info == '8407':
	    		self.is_initialized = True

	    return self.is_initialized

	def translate_command(self):
		pass

	def check_coordinates(self):
		pass

	def sync_coordinates(self):
		pass

	def check_slewing(self):
		# First send the command to get slewing statusonM
		self.send_command(self.get_command('slewing'))
		self.is_slewing = self.read_response()
		return self.is_slewing

	def slew_to_coordinates(self):
		pass

	def slew_to_park(self):
		pass

	def echo(self):
		pass
