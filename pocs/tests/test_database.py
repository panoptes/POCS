import pytest

from pocs.utils.error import InvalidCollection
from pocs.utils.logger import get_root_logger


def test_insert_and_get_current(db):
    rec = {'test': 'insert'}
    db.insert_current('config', rec)

    record = db.get_current('config')
    assert record['data']['test'] == rec['test']


def test_insert_and_no_permanent(db):
    rec = {'test': 'insert'}
    id0 = db.insert_current('config', rec, store_permanently=False)

    record = db.get_current('config')
    assert record['data']['test'] == rec['test']

    record = db.find('config', id0)
    assert record is None


def test_clear_current(db):
    rec = {'test': 'insert'}
    db.insert_current('config', rec)

    record = db.get_current('config')
    assert record['data']['test'] == rec['test']

    db.clear_current('config')

    record = db.get_current('config')
    assert record is None


def test_simple_insert(db):
    rec = {'test': 'insert'}
    # Use `insert` here, which returns an `ObjectId`
    id0 = db.insert('config', rec)

    record = db.find('config', id0)
    assert record['data']['test'] == rec['test']


# Filter out (hide) "UserWarning: Collection not available"
@pytest.mark.filterwarnings('ignore')
def test_bad_collection(db):
    with pytest.raises(InvalidCollection):
        db.insert_current('foobar', {'test': 'insert'})

    with pytest.raises(InvalidCollection):
        db.insert('foobar', {'test': 'insert'})


def test_log_bad_object(db, caplog):
    if not db.logger:
        db.logger = get_root_logger()

    assert db.insert_current('observations', {'junk': db}) is None
    assert any([rec.levelname == 'WARNING' and
                'Problem inserting object into current collection' in rec.message
                for rec in caplog.records])

    caplog.records.clear()

    assert db.insert('observations', {'junk': db}) is None
    assert any([rec.levelname == 'WARNING' and
                'Problem inserting object into collection' in rec.message
                for rec in caplog.records])


def test_warn_bad_object(db):
    db.logger = None

    with pytest.warns(UserWarning):
        db.insert_current('observations', {'junk': db})

    with pytest.warns(UserWarning):
        db.insert('observations', {'junk': db})
