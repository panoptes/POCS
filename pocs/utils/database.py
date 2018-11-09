import abc
import os
import pymongo
import threading
import weakref
from warnings import warn
from uuid import uuid4
from glob import glob
from bson.objectid import ObjectId

from pocs.utils import current_time
from pocs.utils import serializers as json_util
from pocs.utils.config import load_config


class AbstractPanDB(metaclass=abc.ABCMeta):
    def __init__(self, db_name=None, collection_names=list(), logger=None, **kwargs):
        """
        Init base class for db instances.

        Args:
            db_name: Name of the database, typically panoptes or panoptes_testing.
            collection_names (list of str): Names of the valid collections.
            logger: (Optional) logger to use for warnings.
        """
        self.db_name = db_name
        self.collection_names = collection_names
        self.logger = logger

    def _warn(self, *args, **kwargs):
        if self.logger:
            self.logger.warning(*args, **kwargs)
        else:
            warn(*args)

    def validate_collection(self, collection):
        if collection not in self.collection_names:
            msg = 'Collection type {!r} not available'.format(collection)
            self._warn(msg)
            # Can't import pocs.utils.error earlier
            from pocs.utils.error import InvalidCollection
            raise InvalidCollection(msg)

    @abc.abstractclassmethod
    def insert_current(self, collection, obj, store_permanently=True):
        """Insert an object into both the `current` collection and the collection provided.

        Args:
            collection (str): Name of valid collection within the db.
            obj (dict or str): Object to be inserted.
            store_permanently (bool): Whether to also update the collection,
                defaults to True.

        Returns:
            str: identifier of inserted record. If `store_permanently` is True, will
                be the identifier of the object in the `collection`, otherwise will be the
                identifier of object in the `current` collection. These may or
                may not be the same.
                Returns None if unable to insert into the collection.
        """
        raise NotImplementedError

    @abc.abstractclassmethod
    def insert(self, collection, obj):
        """Insert an object into the collection provided.

        The `obj` to be stored in a collection should include the `type`
        and `date` metadata as well as a `data` key that contains the actual
        object data. If these keys are not provided then `obj` will be wrapped
        in a corresponding object that does contain the metadata.

        Args:
            collection (str): Name of valid collection within the db.
            obj (dict or str): Object to be inserted.

        Returns:
            str: identifier of inserted record in `collection`.
                Returns None if unable to insert into the collection.
        """
        raise NotImplementedError

    @abc.abstractclassmethod
    def get_current(self, collection):
        """Returns the most current record for the given collection

        Args:
            collection (str): Name of the collection to get most current from

        Returns:
            dict|None: Current object of the collection or None.
        """
        raise NotImplementedError

    @abc.abstractclassmethod
    def find(self, collection, obj_id):
        """Find an object by it's identifier.

        Args:
            collection (str): Collection to search for object.
            obj_id (ObjectID|str): Record identifier returned earlier by insert
                or insert_current.

        Returns:
            dict|None: Object matching identifier or None.
        """
        raise NotImplementedError

    @abc.abstractclassmethod
    def clear_current(self, type):
        """Clear the current record of a certain type

        Args:
            type (str): The type of entry in the current collection that
                should be cleared.
        """
        raise NotImplementedError


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

    client = pymongo.MongoClient(host, port, connect=connect)

    _shared_mongo_clients[key] = client
    return client


def create_storage_obj(collection, data, obj_id=None):
    """Returns the object to be stored in the database"""
    obj = dict(data=data, type=collection, date=current_time(datetime=True))
    if obj_id:
        obj['_id'] = obj_id
    return obj


class PanDB(object):
    """Simple class to load the appropriate DB type based on the config.

    We don't actually create instances of this class, but instead create
    an instance of the 'correct' type of db.
    """

    def __new__(cls, db_type=None, db_name=None, *args, **kwargs):
        """Create an instance based on db_type."""

        if not isinstance(db_name, str) and db_name:
            raise ValueError('db_name, a string, must be provided and not empty')

        if db_type is None:
            db_type = load_config()['db']['type']

        if not isinstance(db_type, str) and db_type:
            raise ValueError('db_type, a string, must be provided and not empty')

        collection_names = PanDB.collection_names()

        if db_type == 'mongo':
            try:
                return PanMongoDB(collection_names=collection_names, **kwargs)
            except Exception:
                raise Exception(
                    "Can't connect to mongo, please check settings or change DB storage type")
        elif db_type == 'file':
            return PanFileDB(collection_names=collection_names, **kwargs)
        elif db_type == 'memory':
            return PanMemoryDB.get_or_create(collection_names=collection_names, **kwargs)
        else:
            raise Exception('Unsupported database type: {}', db_type)

    @staticmethod
    def collection_names():
        """The pre-defined list of collections that are valid."""
        return [
            'camera_board',
            'config',
            'current',
            'drift_align',
            'environment',
            'mount',
            'observations',
            'offset_info',
            'power',
            'state',
            'telemetry_board',
            'weather',
        ]

    @classmethod
    def permanently_erase_database(cls, db_type, db_name, really=False, dangerous=False, *args, **kwargs):
        """Permanently delete the contents of the identified database."""
        if not isinstance(db_type, str) and db_type:
            raise ValueError('db_type, a string, must be provided and not empty; was {!r}',
                             db_type)
        if not isinstance(db_name, str) or 'test' not in db_name:
            raise ValueError(
                'permanently_erase_database() called for non-test database {!r}'.format(db_name))
        if really != 'Yes' or dangerous != 'Totally':
            raise Exception('PanDB.permanently_erase_database called with invalid args!')
        if db_type == 'mongo':
            PanMongoDB.permanently_erase_database(db_name, *args, **kwargs)
        elif db_type == 'file':
            PanFileDB.permanently_erase_database(db_name, *args, **kwargs)
        elif db_type == 'memory':
            PanMemoryDB.permanently_erase_database(db_name, *args, **kwargs)
        else:
            raise Exception('Unsupported database type: {}', db_type)


class PanMongoDB(AbstractPanDB):
    def __init__(self, db_name='panoptes', host='localhost', port=27017, connect=False, **kwargs):
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
            db_name (str, optional): Name of the database containing the collections.
            host (str, optional): hostname running MongoDB.
            port (int, optional): port running MongoDb.
            connect (bool, optional): Connect to mongo on create, defaults to True.
        """

        super().__init__(**kwargs)

        # Get the mongo client.
        self._client = get_shared_mongo_client(host, port, connect)

        # Create an attribute on the client with the db name.
        db_handle = self._client[db_name]

        # Setup static connections to the collections we want.
        for collection in self.collection_names:
            # Add the collection as an attribute.
            setattr(self, collection, getattr(db_handle, collection))

    def insert_current(self, collection, obj, store_permanently=True):
        self.validate_collection(collection)
        obj = create_storage_obj(collection, obj)
        try:
            # Update `current` record. If one doesn't exist, insert one. This
            # combo is known as UPSERT (i.e. UPDATE or INSERT).
            upsert = True
            obj_id = self.current.replace_one({'type': collection}, obj, upsert).upserted_id
            if not store_permanently and not obj_id:
                # There wasn't a pre-existing record, so upserted_id was None.
                obj_id = self.get_current(collection)['_id']
        except Exception as e:
            self._warn("Problem inserting object into current collection: {}, {!r}".format(e, obj))
            obj_id = None

        if store_permanently:
            try:
                col = getattr(self, collection)
                obj_id = col.insert_one(obj).inserted_id
            except Exception as e:
                self._warn("Problem inserting object into collection: {}, {!r}".format(e, obj))
                obj_id = None

        if obj_id:
            return str(obj_id)
        return None

    def insert(self, collection, obj):
        self.validate_collection(collection)
        try:
            obj = create_storage_obj(collection, obj)
            # Insert record into db
            col = getattr(self, collection)
            return col.insert_one(obj).inserted_id
        except Exception as e:
            self._warn("Problem inserting object into collection: {}, {!r}".format(e, obj))
            return None

    def get_current(self, collection):
        return self.current.find_one({'type': collection})

    def find(self, collection, obj_id):
        collection = getattr(self, collection)
        if isinstance(obj_id, str):
            obj_id = ObjectId(obj_id)
        return collection.find_one({'_id': obj_id})

    def clear_current(self, type):
        self.current.delete_one({'type': type})

    @classmethod
    def permanently_erase_database(self, db_name):
        # Create an instance of PanMongoDb in order to get access to
        # the relevant client.
        db = PanDB(db_type='mongo', db_name=db_name)
        for collection_name in db.collection_names:
            if not hasattr(db, collection_name):
                db._warn(f'Unable to locate collection {collection_name!r} to erase it.')
                continue
            try:
                collection = getattr(db, collection_name)
                collection.drop()
            except Exception as e:
                db._warn(f'Unable to drop collection {collection_name!r}; exception: {e}.')


class PanFileDB(AbstractPanDB):
    """Stores collections as files of JSON records."""

    def __init__(self, db_name='panoptes', **kwargs):
        """Flat file storage for json records

        This will simply store each json record inside a file corresponding
        to the type. Each entry will be stored in a single line.
        Args:
            db_name (str, optional): Name of the database containing the collections.
        """

        super().__init__(db_name=db_name, **kwargs)

        self.db_folder = db_name

        # Set up storage directory.
        self._storage_dir = os.path.join(os.environ['PANDIR'], 'json_store', self.db_folder)
        os.makedirs(self._storage_dir, exist_ok=True)

    def insert_current(self, collection, obj, store_permanently=True):
        self.validate_collection(collection)
        obj_id = self._make_id()
        obj = create_storage_obj(collection, obj, obj_id=obj_id)
        current_fn = self._get_file(collection, permanent=False)
        result = obj_id
        try:
            # Overwrite current collection file with obj.
            json_util.dumps_file(current_fn, obj, clobber=True)
        except Exception as e:
            self._warn("Problem inserting object into current collection: {}, {!r}".format(e, obj))
            result = None

        if not store_permanently:
            return result

        collection_fn = self._get_file(collection)
        try:
            # Append obj to collection file.
            json_util.dumps_file(collection_fn, obj)
            return obj_id
        except Exception as e:
            self._warn("Problem inserting object into collection: {}, {!r}".format(e, obj))
            return None

    def insert(self, collection, obj):
        self.validate_collection(collection)
        obj_id = self._make_id()
        obj = create_storage_obj(collection, obj, obj_id=obj_id)
        collection_fn = self._get_file(collection)
        try:
            # Insert record into file
            json_util.dumps_file(collection_fn, obj)
            return obj_id
        except Exception as e:
            self._warn("Problem inserting object into collection: {}, {!r}".format(e, obj))
            return None

    def get_current(self, collection):
        current_fn = self._get_file(collection, permanent=False)

        try:
            return json_util.loads_file(current_fn)
        except FileNotFoundError:
            self._warn("No record found for {}".format(collection))
            return None

    def find(self, collection, obj_id):
        collection_fn = self._get_file(collection)
        with open(collection_fn, 'r') as f:
            for line in f:
                # Note: We can speed this up for the case where the obj_id doesn't
                # contain any characters that json would need to escape: first
                # check if the line contains the obj_id; if not skip. Else, parse
                # as json, and then check for the _id match.
                obj = json_util.loads(line)
                if obj['_id'] == obj_id:
                    return obj
        return None

    def clear_current(self, type):
        current_f = os.path.join(self._storage_dir, 'current_{}.json'.format(type))
        try:
            os.remove(current_f)
        except FileNotFoundError:
            pass

    def _get_file(self, collection, permanent=True):
        if permanent:
            name = '{}.json'.format(collection)
        else:
            name = 'current_{}.json'.format(collection)
        return os.path.join(self._storage_dir, name)

    def _make_id(self):
        return str(uuid4())

    @classmethod
    def permanently_erase_database(cls, db_name):
        # Clear out any .json files.
        storage_dir = os.path.join(os.environ['PANDIR'], 'json_store', db_name)
        for f in glob(os.path.join(storage_dir, '*.json')):
            os.remove(f)


class PanMemoryDB(AbstractPanDB):
    """In-memory store of serialized objects.

    We serialize the objects in order to test the same code path used
    when storing in an external database.
    """

    active_dbs = weakref.WeakValueDictionary()

    @classmethod
    def get_or_create(cls, db_name=None, **kwargs):
        """Returns the named db, creating if needed.

        This method exists because PanDB gets called multiple times for
        the same database name. With mongo or a file store where the storage
        is external from the instance, that is not a problem, but with
        PanMemoryDB the instance is the store, so the instance must be
        shared."""
        db = PanMemoryDB.active_dbs.get(db_name)
        if not db:
            db = PanMemoryDB(db_name=db_name, **kwargs)
            PanMemoryDB.active_dbs[db_name] = db
        return db

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current = {}
        self.collections = {}
        self.lock = threading.Lock()

    def _make_id(self):
        return str(uuid4())

    def insert_current(self, collection, obj, store_permanently=True):
        self.validate_collection(collection)
        obj_id = self._make_id()
        obj = create_storage_obj(collection, obj, obj_id=obj_id)
        try:
            obj = json_util.dumps(obj)
        except Exception as e:
            self._warn("Problem inserting object into current collection: {}, {!r}".format(e, obj))
            return None
        with self.lock:
            self.current[collection] = obj
            if store_permanently:
                self.collections.setdefault(collection, {})[obj_id] = obj
        return obj_id

    def insert(self, collection, obj):
        self.validate_collection(collection)
        obj_id = self._make_id()
        obj = create_storage_obj(collection, obj, obj_id=obj_id)
        try:
            obj = json_util.dumps(obj)
        except Exception as e:
            self._warn("Problem inserting object into collection: {}, {!r}".format(e, obj))
            return None
        with self.lock:
            self.collections.setdefault(collection, {})[obj_id] = obj
        return obj_id

    def get_current(self, collection):
        with self.lock:
            obj = self.current.get(collection, None)
        if obj:
            obj = json_util.loads(obj)
        return obj

    def find(self, collection, obj_id):
        with self.lock:
            obj = self.collections.get(collection, {}).get(obj_id)
        if obj:
            obj = json_util.loads(obj)
        return obj

    def clear_current(self, entry_type):
        try:
            del self.current[entry_type]
        except KeyError as e:
            pass

    @classmethod
    def permanently_erase_database(self, db_name):
        # For some reason we're not seeing all the references disappear
        # after tests. Perhaps there is some global variable pointing at
        # the db or one of its referrers, or perhaps a pytest fixture
        # hasn't been removed.
        PanMemoryDB.active_dbs = weakref.WeakValueDictionary()
