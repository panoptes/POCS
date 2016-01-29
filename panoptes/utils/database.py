import pymongo


class PanMongo(object):

    """ Connection to the running MongoDB instance

    This is a collection of parameters that are initialized when the unit
    starts and can be read and updated as the project is running. The server
    is a wrapper around a mongodb collection.
    """

    def __init__(self, host='localhost', port=27017):
        # Get the mongo client
        self._client = pymongo.MongoClient(host, port)

        # Setup static connections to the collections we want
        self.sensors = self._client.panoptes.sensors
        self.state_information = self._client.panoptes.state_information
        self.images = self._client.panoptes.images
        self.observations = self._client.panoptes.observations
        self.mount_info = self._client.panoptes.mount_info
        # self.admin = self._client.panoptes.admin
        # self.config = self._client.panoptes.config
        # self.params = self._client.panoptes.params

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
            param = self._db.param_server.find_one({key: {'$exists': True}})
            val = param.get(key)

        return val
