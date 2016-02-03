

"""
Command-line application that streams data into BigQuery.
This sample is used on this page:
    https://cloud.google.com/bigquery/streaming-data-into-bigquery
For more information, see the README.md under /bigquery.

"""

import uuid

from googleapiclient import discovery
from oauth2client.client import GoogleCredentials

from ..logger import get_logger


class PanBigQuery(object):
    """ Class for interacting with Google BigQuery """
    def __init__(self, project_id):
        super(PanBigQuery, self).__init__()
        self.logger = get_logger(self)
        self.project_id = project_id
        # Grab the application's default credentials from the environment.
        self.credentials = GoogleCredentials.get_application_default()

        # Construct the service object for interacting with the BigQuery API.
        self._bq = discovery.build('bigquery', 'v2', credentials=self.credentials)

    def stream_row_to_bigquery(self, dataset_id, table_name, row, num_retries=5):
        """ Sends data to bigquery

        Note:
            A unique id is generated for the row so that duplicate inserts are not performed.

        Args:
            dataset_id(str):    Name of dataset to perform actions on.
            table_name(str):    Table for query. Table must belong to `dataset_id`.
            row(object):        Data to be inserted.
            num_retries(Optional[int]): Number of times to attempt reinsert. Defaults to 5.

        Returns:
            bool:   Indicating success
        """
        insert_all_data = {
            'insertId': str(uuid.uuid4()),
            'rows': [{'json': row}]
        }
        self.logger.debug("BQ Data: {}".format(insert_all_data))

        table_result = self._bq.tabledata().insertAll(
            projectId=self.project_id,
            datasetId=dataset_id,
            tableId=table_name,
            body=insert_all_data).execute(num_retries=num_retries)

        self.logger.debug("BQ Insert: {}".format(table_result))

        return table_result

    def _new_table(self, dataset_id, table_name, schema, desc=""):
        """ Creates a new table for the given dataset

        """
        assert schema is not None, self.logger.warning("Must pass schema with new table")
        self.logger.debug("BQ New Table Name: {}".format(table_name))

        table_id = table_name.casefold().replace(' ', '-')

        table_body = {
            "tableReference": {
                "projectId": self.project_id,
                "datasetId": dataset_id,
                "tableId": table_id,
            },
            "schema": schema,
            "description": desc,
            "friendlyName": table_name,

        }

        self.logger.debug("BQ New Table Data: {}".format(table_body))

        table_result = {}

        try:
            table_result = self._bq.tables().insert(
                projectId=self.project_id,
                datasetId=dataset_id,
                body=table_body,
            ).execute()
        except Exception as e:
            self.logger.warning("Problem with BQ: {}".format(e))

        self.logger.debug("BQ New Table ID: {}".format(table_result.get('id')))

        return table_result
