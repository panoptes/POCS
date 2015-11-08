import pytest

from astropy.time import Time
from astropy.tests.helper import remote_data
from ..utils.google.bigquery import PanBigQuery


now = Time.now().isot
table_name = 'test_sandbox_{}'.format(now.split('T')[0].replace('-', '_'))
dataset_id = 'playground'


class TestBiqQuery(object):

    @remote_data
    def test_new_table(self):
        bq = PanBigQuery('panoptes-survey')

        schema = {
            "fields": [
                {"type": "STRING", "name": "unit"},
                {"type": "TIMESTAMP", "name": "ts"},
                {"type": "STRING", "name": "state"}
            ]
        }

        result = bq._new_table(dataset_id, table_name, schema)

        assert result.get('id') is not None

    @remote_data
    def test_insert_data(self):
        bq = PanBigQuery('panoptes-survey')

        row = {
            "unit": 'PAN001',
            "ts": now,
            "state": "parked",
        }
        result = bq.stream_row_to_bigquery(dataset_id, table_name, row)

        assert result.get('insertErrors') is None
