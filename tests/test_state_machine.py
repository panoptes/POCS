from unittest.mock import MagicMock, patch

import pytest

from panoptes.utils import error
from panoptes.utils.serializers import to_yaml

from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory


@pytest.fixture
def observatory():
    observatory = Observatory(simulator=["all"])

    yield observatory


@pytest.fixture
def pocs(observatory):
    pocs = POCS(observatory)

    yield pocs

    pocs.connected = False


def test_bad_state_machine_file():
    with pytest.raises(error.InvalidConfig):
        POCS.load_state_table(state_table_name="foo")


def test_init_raises_for_missing_states(observatory, tmp_path):
    state_machine_file = tmp_path / "missing_states.yaml"
    state_machine_file.write_text(to_yaml({"transitions": []}))

    with pytest.raises(error.InvalidConfig, match="missing required 'states' section"):
        POCS(observatory, state_machine_file=str(state_machine_file.resolve()))


def test_init_raises_for_missing_transitions(observatory, tmp_path):
    state_machine_file = tmp_path / "missing_transitions.yaml"
    state_machine_file.write_text(to_yaml({"states": {}}))

    with pytest.raises(error.InvalidConfig, match="missing required 'transitions' section"):
        POCS(observatory, state_machine_file=str(state_machine_file.resolve()))


def test_load_bad_state(pocs):
    with pytest.raises(error.InvalidConfig):
        pocs._load_state("foo")


def test_load_state_info(pocs):
    pocs._load_state("ready", state_info={"tags": ["at_twilight"]})


def test_next_state_property(pocs):
    pocs.next_state = "observing"

    assert pocs.next_state == "observing"


def test_interrupted_logs_critical_message(pocs, caplog):
    pocs.interrupted = True

    assert pocs.interrupted is True
    assert caplog.records[-1].levelname == "CRITICAL"
    assert caplog.records[-1].message == "POCS has been interrupted"


def test_lookup_trigger_default_park(pocs, caplog):
    pocs._load_state("ready", state_info={"tags": ["at_twilight"]})
    pocs.state = "ready"
    pocs.next_state = "foobar"

    next_state = pocs._lookup_trigger()

    assert next_state == "parking"
    assert caplog.records[-1].levelname == "WARNING"
    assert caplog.records[-1].message == "No transition for ready -> foobar, going to park"


def test_lookup_trigger_returns_set_park_when_already_parking(pocs):
    pocs.state = "parking"
    pocs.next_state = "parking"

    assert pocs._lookup_trigger() == "set_park"


def test_state_machine_absolute(tmp_path):
    state_table = POCS.load_state_table()
    assert isinstance(state_table, dict)

    state_machine_file = tmp_path / "state_table.yaml"
    state_machine_file.write_text(to_yaml(state_table))

    assert POCS.load_state_table(state_table_name=str(state_machine_file.resolve()))


def test_stop_states_sets_do_states_false(pocs):
    pocs.do_states = True

    pocs.stop_states()

    assert pocs.do_states is False


def test_check_safety_without_event_data_calls_is_safe(pocs):
    with patch.object(pocs, "is_safe", return_value=True) as mock_is_safe:
        assert pocs.check_safety() is True

    mock_is_safe.assert_called_once_with()


def test_check_safety_allows_always_safe_states_without_safety_check(pocs):
    event_data = MagicMock()
    event_data.transition.dest = "parking"

    with patch.object(pocs, "is_safe", return_value=False) as mock_is_safe:
        assert pocs.check_safety(event_data=event_data) is True

    mock_is_safe.assert_not_called()


def test_check_safety_checks_non_always_safe_states(pocs):
    event_data = MagicMock()
    event_data.transition.dest = "observing"
    pocs._horizon_lookup["observing"] = "custom-horizon"

    with patch.object(pocs, "is_safe", return_value=False) as mock_is_safe:
        assert pocs.check_safety(event_data=event_data) is False

    mock_is_safe.assert_called_once_with(horizon="custom-horizon")


def test_load_transition_prepends_check_safety(pocs):
    transition = {"source": ["ready"], "dest": "observing", "conditions": ["mount_is_initialized"]}

    loaded_transition = pocs._load_transition(transition)

    assert loaded_transition["conditions"] == ["check_safety", "mount_is_initialized"]


def test_load_transition_adds_default_condition(pocs):
    transition = {"source": ["ready"], "dest": "observing"}

    loaded_transition = pocs._load_transition(transition)

    assert loaded_transition["conditions"] == ["check_safety"]
