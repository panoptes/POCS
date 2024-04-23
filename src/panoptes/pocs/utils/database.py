import warnings

from panoptes.utils.config.client import get_config
from panoptes.utils.database.file import PanFileDB

try:
    from google.cloud import firestore
except (ImportError, ValueError):
    warnings.warn('google-cloud-firestore module is missing, full DB features unavailable')
    firestore = None

from loguru import logger


class PocsDB(PanFileDB):
    """PanFileDB wrapper that also writes to Firestore."""

    def __init__(self, *args, **kwargs):
        self.unit_id = get_config('pan_id')
        if self.unit_id is None:
            raise ValueError(f'PocsDB requires a `pan_id` item in the config')

        self.firestore_db = None
        self.use_firestore = False

        super(PocsDB, self).__init__(*args, **kwargs)

        # Set up Firestore if config is set.
        self.check_firestore()

    def check_firestore(self):
        """Check if we should use firestore or not."""
        if firestore is None:
            self.firestore_db = None
            return

        self.use_firestore = get_config('panoptes_network.use_firestore', default=False)
        if self.use_firestore:
            logger.info('Setting up Firestore connection')
            self.firestore_db = firestore.Client()
        else:
            self.firestore_db = None

    def insert_current(self, collection, obj, store_permanently=True):
        """Inserts into the current collection locally and on firestore db."""
        return super().insert_current(collection, obj, store_permanently=store_permanently)

    def insert(self, collection, obj):
        """Insert document into either the firestore db or a local file."""
        obj_id = None

        if self.use_firestore:
            try:
                # Add a document.
                fs_key = f'metadata/{collection}'

                record = {
                    'received_time': firestore.SERVER_TIMESTAMP,
                    'unit': self.firestore_db.document(f'/units/{self.unit_id}'),
                    **obj
                }

                doc_ts, obj_id = self.firestore_db.collection(fs_key).add(record)
            except Exception as e:
                logger.warning(f'Problem inserting record into firestore: {e}')
        else:
            obj_id = super().insert(collection, obj)

        return obj_id
