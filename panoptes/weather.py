import panoptes.utils.logger as logger

@logger.has_logger
class WeatherStation():
	"""
	Main weather station class
	"""

	def __init__(self):

		self.logger.info('Starting WeatherStation')