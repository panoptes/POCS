from panoptes.mount.mount import AbstractMount
import panoptes.utils.logger as logger

@logger.do_logging
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
