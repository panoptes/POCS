import panoptes.utils.logger as logger

@logger.do_logging
class Error(Exception):
	""" Base class for Panoptes errors """
	pass

class InvalidConfig(Error):
	""" Error raised if config file is invalid """
	def __init__(self, msg='Error'):
		super(InvalidConfig, self).__init__()
		self.msg = msg

	def __str__(self):
		return self.msg
		