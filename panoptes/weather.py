import panoptes.utils.logger as logger

class WeatherStation():
	"""
	Main weather station class
	"""

	def __init__(self, log=None):

	    self.logger = log or logger.Logger()