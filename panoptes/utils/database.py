import pymongo
from ..utils import current_time


class PanMongo(object):

    """ Connection to the running MongoDB instance

    This is a collection of parameters that are initialized when the unit
    starts and can be read and updated as the project is running. The server
    is a wrapper around a mongodb collection.
    """

    def __init__(self, host='localhost', port=27017):
        # Get the mongo client
        self._client = pymongo.MongoClient(host, port)

        collections = [
            'camera',
            'config',
            'current',
            'environment',
            'images',
            'mount',
            'visits',
            'state',
            'target',
            'weather',
        ]

        # Setup static connections to the collections we want
        for collection in collections:
            # Add the collection as an attribute
            setattr(self, collection, getattr(self._client.panoptes, 'panoptes.{}'.format(collection)))

    def insert_current(self, collection, obj):

        col = getattr(self, collection)

        current_obj = {
            'type': collection,
            'data': obj,
            'date': current_time(utcnow=True),
        }

        # Update `current` record
        self.current.replace_one({'type': collection}, current_obj, True)

        # Insert record into db
        col.insert_one(current_obj)

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
