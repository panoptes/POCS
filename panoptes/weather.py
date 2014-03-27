import panoptes.utils.logger as logger

class WeatherStation():
	"""
	Main weather station class
	"""

	def __init__(self,**kwargs):
	    if kwargs['logger']:
	        self.logger = kwargs['logger']
	    else:
	        self.logger = logger.Logger()   		