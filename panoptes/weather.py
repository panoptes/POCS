import panoptes.utils.logger as logger

@logger.do_logging
class WeatherStation():
	"""
	Main weather station class
	"""

	def __init__(self):

		self.logger.info('Starting WeatherStation')