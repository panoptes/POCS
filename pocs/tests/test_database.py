import pytest


def test_insert_and_get_current(db):
    rec = {'test': 'insert'}
    db.insert_current('config', rec)

    record = db.config.find_one({'data.test': {'$exists': 1}})
    assert record['data']['test'] == rec['test']

    record = db.current.find_one({'type': 'config'})
    assert record['data']['test'] == rec['test']

    record = db.get_current('config')
    assert record['data']['test'] == rec['test']

    db.config.remove({'data.test': 'insert'})
    record = db.config.find({'data.test': {'$exists': 1}})
    assert record.count() == 0

    db.current.remove({'type': 'config'})


def test_insert_and_no_collection(db):
    rec = {'test': 'insert'}
    db.insert_current('config', rec, include_collection=False)

    record = db.get_current('config')
    assert record['data']['test'] == rec['test']

    record = db.config.find({'data.test': {'$exists': 1}})
    assert record.count() == 0

    db.current.remove({'type': 'config'})


def test_simple_insert(db):
    rec = {'test': 'insert'}
    db.insert('config', rec)

    record = db.config.find({'data.test': {'$exists': 1}})
    assert record.count() == 1

    db.current.remove({'type': 'config'})


# Filter out (hide) "UserWarning: Collection not available"
@pytest.mark.filterwarnings('ignore')
def test_bad_collection(db):
    with pytest.raises(AssertionError):
        db.insert_current('foobar', {'test': 'insert'})

    with pytest.raises(AssertionError):
        db.insert('foobar', {'test': 'insert'})


def test_bad_object(db):
    with pytest.warns(UserWarning):
        db.insert_current('observations', {'junk': db})

    with pytest.warns(UserWarning):
        db.insert('observations', {'junk': db})
