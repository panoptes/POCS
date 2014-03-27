import panoptes.utils.logger as logger

class Camera:
	"""
	Main camera class
	"""

	def __init__(self,**kwargs):
	    if kwargs['logger']:
	        self.logger = kwargs['logger']
	    else:
	        self.logger = logger.Logger()   