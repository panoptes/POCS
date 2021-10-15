from google.cloud import firestore
from panoptes.utils.config.client import get_config
from panoptes.utils.database.file import PanFileDB


class PocsDB(PanFileDB):
    """PanFileDB wrapper that also writes to Firestore."""

    def __init__(self, *args, **kwargs):
        self.unit_id = get_config('pan_id')
        if self.unit_id is None:
            raise ValueError(f'PocsDB requires a `pan_id` item in the config')

        self.firestore_db = firestore.Client()

        super(PocsDB, self).__init__(*args, **kwargs)

    def insert_current(self, collection, obj, store_permanently=True):
        """Inserts into the current collection locally and on firestore db."""
        obj_id = super().insert_current(collection, obj, store_permanently=store_permanently)

        if get_config('panoptes_network.use_firestore'):
            obj['received_time'] = firestore.SERVER_TIMESTAMP

            # Update the "current" collection.
            current_doc = self.firestore_db.document(f'/units/{self.unit_id}/current/{collection}')
            current_doc.set(obj)

            obj_id = self.insert(collection, obj)

        return obj_id

    def insert(self, collection, obj):
        """Insert document into local file and firestore db."""
        obj_id = super().insert(collection, obj)

        if get_config('panoptes_network.use_firestore'):
            if 'received_time' not in obj:
                obj['received_time'] = firestore.SERVER_TIMESTAMP

            # Add a document.
            col = self.firestore_db.collection(f'/units/{self.unit_id}/metadata/')
            doc_ts, obj_id = col.add(obj, document_id=collection)

        return obj_id
