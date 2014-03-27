import panoptes.utils.logger as logger

class Camera:
	"""
	Main camera class
	"""

	def __init__(self,logger=None):

	    self.logger = logger or logger.Logger()