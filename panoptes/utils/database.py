import pymongo
import warnings
from ..utils import current_time

from datetime import date, datetime
from bson import json_util
import json
import gzip

from astropy import units as u


class PanMongo(object):

    """ Connection to the running MongoDB instance

    This is a collection of parameters that are initialized when the unit
    starts and can be read and updated as the project is running. The server
    is a wrapper around a mongodb collection.
    """

    def __init__(self, host='localhost', port=27017, connect=False):
        # Get the mongo client
        self._client = pymongo.MongoClient(host, port, connect=connect)

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

    def export(self, yesterday=True, start_date=None, end_date=None, database=None, collections=list(), **kwargs):

        if yesterday:
            start_dt = (current_time() - 1. * u.day).datetime
            start = datetime(start_dt.year, start_dt.month, start_dt.day, 0, 0, 0, 0)
            end = datetime(start_dt.year, start_dt.month, start_dt.day, 23, 59, 59, 0)
        else:
            assert start_date, warnings.warn("start-date required if not using yesterday")

            y, m, d = [int(x) for x in start_date.split('-')]
            start_dt = date(y, m, d)

            if end_date is None:
                end_dt = start_dt
            else:
                y, m, d = [int(x) for x in end_date.split('-')]
                end_dt = date(y, m, d)

            start = datetime.fromordinal(start_dt.toordinal())
            end = datetime(end_dt.year, end_dt.month, end_dt.day, 23, 59, 59, 0)

        for collection in collections:
            start_str = start.strftime('%Y-%m-%d')
            end_str = end.strftime('%Y-%m-%d')
            if end_str != start_str:
                out_file = '/var/panoptes/backups/{}_{}-to-{}.json'.format(collection, start_str, end_str)
            else:
                out_file = '/var/panoptes/backups/{}_{}.json'.format(collection, start_str)

            col = getattr(self, collection)
            entries = [x for x in col.find({'date': {'$gt': start, '$lt': end}}).sort([('date', pymongo.ASCENDING)])]

            if len(entries):
                content = json.dumps(entries, default=json_util.default)
                write_type = 'w'

                if kwargs.get('gzip', False):
                    content = gzip.compress(bytes(content, 'utf8'))
                    out_file = out_file + '.gz'
                    write_type = 'wb'

                with open(out_file, write_type)as f:
                    f.write(content)
