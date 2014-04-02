import panoptes.utils.logger as logger

@logger.has_logger
class Camera:
	"""
	Main camera class
	"""

	def __init__(self):
		self.logger.info('Setting up Camera')