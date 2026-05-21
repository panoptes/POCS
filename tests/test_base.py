from panoptes.utils.telemetry import TelemetryClient

from panoptes.pocs.base import PanBase


def test_with_logger():
    PanBase()


def test_with_db():
    base = PanBase(db=TelemetryClient())
    assert isinstance(base, PanBase)
    assert isinstance(base.db, TelemetryClient)


def test_remember_config():
    base = PanBase()
    location1 = base.get_config(key="location", remember=False)
    location2 = base.get_config(key="location", remember=True)

    assert location1 == location2
