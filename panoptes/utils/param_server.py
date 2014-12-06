from pymongo import MongoClient

class ParamServer(object):
	""" A common collection of parameters for a running Panoptes unit.

	This is a collection of parameters that are initialized when the unit
	starts and can be read and updated as the project is running. The server
	is a wrapper around a mongodb collection.
	"""

	def __init__(self, host='localhost', port=27017):
		# Get the mongo client
		self.client = MongoClient(host, port)
		self.db = self.client.panoptes
		self.param_server = self.db.param_server

	def get_param(self, key=None):
		""" Gets a value from the param server.

		Args:
			key: name of parameter.

		Returns:
			A value for the named parameter. This can be any object that
			is stored in a dict. If no key is specified, warning is given
			and nothing is returned.
		"""

		val = None

		if key is not None:
			param = self.param_server.find_one({ key: { '$exists': True } })
			val = param.get(key)

		return val