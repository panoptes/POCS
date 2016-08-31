import os
import pymongo
import warnings

from ..utils import current_time

import gzip
import json

from bson import json_util
from datetime import date
from datetime import datetime

from astropy import units as u
from astropy.utils import console


class PanMongo(object):

    """ Connection to the running MongoDB instance

    This is a collection of parameters that are initialized when the unit
    starts and can be read and updated as the project is running. The server
    is a wrapper around a mongodb collection.
    """

    def __init__(self, host='localhost', port=27017, connect=False, **kwargs):
        # Get the mongo client
        self._client = pymongo.MongoClient(host, port, connect=connect)

        self.collections = [
            'config',
            'current',
            'environment',
            'mount',
            'observations',
            'state',
            'weather',
        ]

        # Setup static connections to the collections we want
        for collection in self.collections:
            # Add the collection as an attribute
            setattr(self, collection, getattr(self._client.panoptes, 'panoptes.{}'.format(collection)))

        self._backup_dir = kwargs.get(
            'backup_dir', '{}/backups/'.format(os.getenv('PANDIR', default='/var/panoptes/')))

    def insert_current(self, collection, obj):

        if collection in self.collections:
            col = getattr(self, collection)

            current_obj = {
                'type': collection,
                'data': obj,
                'date': current_time(datetime=True),
            }

            # Update `current` record
            self.current.replace_one({'type': collection}, current_obj, True)

            # Insert record into db
            col.insert_one(current_obj)

    def export(self,
               yesterday=True,
               start_date=None,
               end_date=None,
               database=None,
               collections=list(),
               **kwargs):

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

        if 'all' in collections:
            collections = self.collections

        date_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        if end_str != date_str:
            date_str = '{}_to_{}'.format(date_str, end_str)

        out_files = list()

        console.color_print("Exporting collections: ", 'default', "\t{}".format(date_str.replace('_', ' ')), 'yellow')
        for collection in collections:
            if collection not in self.collections:
                next
            console.color_print("\t{}".format(collection))

            out_file = '{}{}_{}.json'.format(self._backup_dir, date_str.replace('-', ''), collection)

            col = getattr(self, collection)
            entries = [x for x in col.find({'date': {'$gt': start, '$lt': end}}).sort([('date', pymongo.ASCENDING)])]

            if len(entries):
                console.color_print("\t\t{} records exported".format(len(entries)), 'yellow')
                content = json.dumps(entries, default=json_util.default)
                write_type = 'w'

                # Assume compression but allow for not
                if kwargs.get('compress', True):
                    console.color_print("\t\tCompressing...", 'lightblue')
                    content = gzip.compress(bytes(content, 'utf8'))
                    out_file = out_file + '.gz'
                    write_type = 'wb'

                with open(out_file, write_type)as f:
                    console.color_print("\t\tWriting file: ", 'lightblue', out_file, 'yellow')
                    f.write(content)

                out_files.append(out_file)

        return out_files
