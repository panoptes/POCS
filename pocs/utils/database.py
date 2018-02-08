import os
import pymongo
import weakref
from warnings import warn
from uuid import uuid4
from glob import glob

from pocs.utils import current_time
from pocs.utils import serializers as json_util
from pocs.utils.config import load_config

_shared_mongo_clients = weakref.WeakValueDictionary()


def get_shared_mongo_client(host, port, connect):
    global _shared_mongo_clients
    key = (host, port, connect)
    try:
        client = _shared_mongo_clients[key]
        if client:
            return client
    except KeyError:
        pass

    client = pymongo.MongoClient(
        host,
        port,
        connect=connect,
        connectTimeoutMS=2500,
        serverSelectionTimeoutMS=2500
    )

    _shared_mongo_clients[key] = client
    return client


class PanDB(object):
    """ Simple class to load the appropriate DB type """

    def __init__(self, db_type=None, logger=None, *args, **kwargs):

        if logger is not None:
            self.logger = logger

        if db_type is None:
            db_type = load_config()['db']['type']

        self.collections = [
            'config',
            'current',
            'drift_align',
            'environment',
            'mount',
            'observations',
            'offset_info',
            'state',
            'weather',
        ]

        self.db = None

        if db_type == 'mongo':
            try:
                self.db = PanMongoDB(
                    collections=self.collections, *args, **kwargs)
            except Exception:
                raise Exception(
                    "Can't connect to mongo, please check settings or change DB storage type")

        if db_type == 'file':
            self.db = PanFileDB(collections=self.collections, *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self.db.insert(*args, **kwargs)

    def insert_current(self, *args, **kwargs):
        return self.db.insert_current(*args, **kwargs)

    def get_current(self, *args, **kwargs):
        return self.db.get_current(*args, **kwargs)

    def find(self, *args, **kwargs):
        return self.db.find(*args, **kwargs)


class PanMongoDB(object):

    def __init__(self,
                 db_name='panoptes',
                 host='localhost',
                 port=27017,
                 connect=False,
                 collections=list(),
                 *args, **kwargs
                 ):
        """Connection to the running MongoDB instance

        This is a collection of parameters that are initialized when the unit
        starts and can be read and updated as the project is running. The server
        is a wrapper around a mongodb collection.

        Note:
            Because mongo can create collections at runtime, the pymongo module
            will also lazily create both databases and collections based off of
            attributes on the client. This means the attributes do not need to
            exist on the client object beforehand and attributes assigned to the
            object will automagically create a database and collection.

            Because of this, we manually store a list of valid collections that
            we want to access so that we do not get spuriously created collections
            or databases.

        Args:
            db_name (str, optional): Name of the database containing the PANOPTES collections.
            host (str, optional): hostname running MongoDB.
            port (int, optional): port running MongoDb.
            connect (bool, optional): Connect to mongo on create, defaults to True.
            logger (None, optional): An instance of the logger.

        """

        # Get the mongo client
        self._client = get_shared_mongo_client(host, port, connect)

        # Pre-defined list of collections that are valid.
        self.collections = collections

        # Create an attribute on the client with the db name.
        db_handle = self._client[db_name]

        # Setup static connections to the collections we want.
        for collection in self.collections:
            # Add the collection as an attribute
            setattr(self, collection, getattr(db_handle, collection))

    def insert_current(self, collection, obj, store_permanently=True):
        """Insert an object into both the `current` collection and the collection provided.

        Args:
            collection (str): Name of valid collection within panoptes db.
            obj (dict or str): Object to be inserted.
            store_permanently (bool): Whether to also update the collection,
                defaults to True.

        Returns:
            str: Mongo object ID of record. If `store_permanently` is True, will
                be the id of the object in the `collection`, otherwise will be the
                id of object in the `current` collection.
        """
        if store_permanently:
            assert collection in self.collections, self._warn(
                "Collection type not available")

        _id = None
        try:
            current_obj = {
                'type': collection,
                'data': obj,
                'date': current_time(datetime=True),
            }

            # Update `current` record
            _id = self.current.replace_one(
                {'type': collection}, current_obj, True  # True for upsert
            ).upserted_id

            if store_permanently:
                _id = self.insert(collection, current_obj)
            elif _id is None:
                _id = self.get_current(collection)['_id']
        except Exception as e:
            self._warn(
                "Problem inserting object into collection: {}, {!r}".format(e, current_obj))

        return str(_id)

    def insert(self, collection, obj):
        """Insert an object into the collection provided.

        The `obj` to be stored in a collection should include the `type`
        and `date` metadata as well as a `data` key that contains the actual
        object data. If these keys are not provided then `obj` will be wrapped
        in a corresponding object that does contain the metadata.

        Args:
            collection (str): Name of valid collection within panoptes db.
            obj (dict or str): Object to be inserted.

        Returns:
            str: Mongo object ID of record in `collection`.
        """
        assert collection in self.collections, self._warn(
            "Collection type not available")

        _id = None
        try:
            # If `data` key is present we assume it has "metadata" (see above).
            if isinstance(obj, dict) and 'data' in obj:
                # But still check for a `type`
                if 'type' not in obj:
                    obj['type'] = collection
            else:
                obj = {
                    'type': collection,
                    'data': obj,
                    'date': current_time(datetime=True),
                }

            # Insert record into db
            col = getattr(self, collection)
            _id = col.insert_one(obj).inserted_id
        except Exception as e:
            self._warn(
                "Problem inserting object into collection: {}, {!r}".format(e, obj))

        return _id

    def get_current(self, collection):
        """Returns the most current record for the given collection

        Args:
            collection (str): Name of the collection to get most current from
        """
        return self.current.find_one({'type': collection})

    def find(self, type, id):
        """Find an object by it's id.

        Args:
            type (str): Collection to search for object.
            id (ObjectID|str): Mongo object id str.

        Returns:
            dict|None: Object matching id or None.
        """
        collection = getattr(self, type)
        return collection.find_one({'_id': id})

    def _warn(self, *args, **kwargs):
        if hasattr(self, 'logger'):
            self.logger.warning(*args, **kwargs)
        else:
            warn(*args)


class PanFileDB(object):

    def __init__(self, db_name='panoptes', collections=list(), *args, **kwargs):
        """Flat file storage for json records

        This will simply store each json record inside a file corresponding
        to the type. Each entry will be stored in a single line.
        """

        self.db_folder = db_name

        # Pre-defined list of collections that are valid.
        self.collections = collections

        # Set up storage directory
        self._storage_dir = '{}/json_store/{}'.format(
            os.environ['PANDIR'], self.db_folder)
        os.makedirs(self._storage_dir, exist_ok=True)

    def insert_current(self, collection, obj, store_permanently=True):
        """Insert an object into both the `current` collection and the collection provided.

        Args:
            collection (str): Name of valid collection within panoptes db.
            obj (dict or str): Object to be inserted.
            store_permanently (bool): Whether to also update the collection,
                defaults to True.

        Returns:
            str: UUID of record. If `store_permanently` is True, will
                be the id of the object in the `collection`, otherwise will be the
                id of object in the `current` collection.
        """
        if store_permanently:
            assert collection in self.collections, self._warn(
                "Collection type not available")

        _id = self._make_id()
        try:
            current_obj = {
                '_id': _id,
                'type': collection,
                'data': obj,
                'date': current_time(datetime=True),
            }

            current_fn = os.path.join(
                self._storage_dir, 'current_{}.json'.format(collection))

            json_util.dumps_file(current_fn, current_obj, clobber=True)

            if store_permanently:
                _id = self.insert(collection, current_obj)
        except Exception as e:
            self._warn(
                "Problem inserting object into collection: {}, {!r}".format(e, current_obj))

        return _id

    def insert(self, collection, obj):
        """Insert an object into the collection provided.

        The `obj` to be stored in a collection should include the `type`
        and `date` metadata as well as a `data` key that contains the actual
        object data. If these keys are not provided then `obj` will be wrapped
        in a corresponding object that does contain the metadata.

        Args:
            collection (str): Name of valid collection within panoptes db.
            obj (dict or str): Object to be inserted.

        Returns:
            str: UUID of record in `collection`.
        """
        assert collection in self.collections, self._warn(
            "Collection type not available")

        _id = self._make_id()
        try:
            # If `data` key is present we assume it has "metadata" (see above).
            if isinstance(obj, dict) and 'data' in obj:
                # But still check for a `type`
                if 'type' not in obj:
                    obj['type'] = collection
            else:
                obj = {
                    '_id': _id,
                    'type': collection,
                    'data': obj,
                    'date': current_time(datetime=True),
                }

            # Insert record into file
            collection_fn = os.path.join(
                self._storage_dir, '{}.json'.format(collection))

            json_util.dumps_file(collection_fn, obj)
        except Exception as e:
            self._warn(
                "Problem inserting object into collection: {}, {!r}".format(e, obj))

        return _id

    def get_current(self, collection):
        """Returns the most current record for the given collection

        Args:
            collection (str): Name of the collection to get most current from

        Returns:
            dict|None: Most recent object of type `collection` or None.
        """
        current_fn = os.path.join(
            self._storage_dir, 'current_{}.json'.format(collection))

        record = dict()

        try:
            record = json_util.loads_file(current_fn)
        except FileNotFoundError as e:
            self._warn("No record found for {}".format(collection))

        return record

    def find(self, type, id):
        """Find an object by it's id.

        Args:
            type (str): Collection to search for object.
            id (ObjectID|str): Mongo object id str.

        Returns:
            dict|None: Object matching `id` or None.
        """
        collection_fn = os.path.join(self._storage_dir, '{}.json'.format(type))

        obj = None
        with open(collection_fn, 'r') as f:
            for line in f:
                temp_obj = json_util.loads(line)
                if temp_obj['_id'] == id:
                    obj = temp_obj
                    break

        return obj

    def _make_id(self):
        return str(uuid4())

    def _warn(self, *args, **kwargs):
        if hasattr(self, 'logger'):
            self.logger.warning(*args, **kwargs)
        else:
            warn(*args)
