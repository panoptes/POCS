import panoptes.utils.logger as logger

class WeatherStation():
	"""
	Main weather station class
	"""

	def __init__(self, logger=None):

        self.logger = logger or logger.Logger()