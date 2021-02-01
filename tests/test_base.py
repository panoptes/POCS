from panoptes.pocs.base import PanBase

from panoptes.utils.database import PanDB


def test_with_logger():
    PanBase()


def test_with_db():
    base = PanBase(db=PanDB(db_type='memory', db_name='tester'))
    assert isinstance(base, PanBase)
