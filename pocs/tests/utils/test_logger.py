import pytest

from panoptes.utils.logger import field_name_to_key
from panoptes.utils.logger import logger_msg_formatter


def test_field_name_to_key():
    assert not field_name_to_key('.')
    assert not field_name_to_key('[')
    assert field_name_to_key('abc') == 'abc'
    assert field_name_to_key(' abc ') == ' abc '
    assert field_name_to_key('abc.def') == 'abc'
    assert field_name_to_key('abc[1].def') == 'abc'


def test_logger_msg_formatter_1_dict():
    d = dict(abc='def', xyz=123)

    tests = [
        # Single anonymous reference, satisfied by the entire dict.
        ('{}', "{'abc': 'def', 'xyz': 123}"),

        # Single anonymous reference, satisfied by the entire dict.
        ('{!r}', "{'abc': 'def', 'xyz': 123}"),

        # Position zero references, satisfied by the entire dict.
        ('{0} {0}', "{'abc': 'def', 'xyz': 123} {'abc': 'def', 'xyz': 123}"),

        # Reference to a valid key in the dict.
        ('{xyz}', "123"),

        # Invalid modern reference, so %s format applied.
        ('%s {1}', "{'abc': 'def', 'xyz': 123} {1}"),

        # Valid legacy format applied to whole dict.
        ('%r', "{'abc': 'def', 'xyz': 123}"),
        ('%%', "%"),
    ]

    for fmt, msg in tests:
        assert logger_msg_formatter(fmt, d) == msg, fmt

    # Now tests with entirely invalid formats, so warnings should be issued.
    tests = [
        '%(2)s',
        '{def}',
        '{def',
        'def}',
        '%d',
        # Bogus references either way.
        '{0} {1} %(2)s'
    ]

    for fmt in tests:
        with pytest.warns(UserWarning):
            assert logger_msg_formatter(fmt, d) == fmt


def test_logger_msg_formatter_1_non_dict():
    d = ['abc', 123]

    tests = [
        # Single anonymous reference, satisfied by first element.
        ('{}', "abc"),

        # Single anonymous reference, satisfied by first element.
        ('{!r}', "'abc'"),

        # Position references, satisfied by elements.
        ('{1} {0!r}', "123 'abc'"),

        # Valid modern reference, %s ignored.
        ('%s {1}', "%s 123"),

        # Valid legacy format applied to whole list.
        ('%r', "['abc', 123]"),

        # Valid legacy format applied to whole list.
        ('%s', "['abc', 123]"),
    ]

    for fmt, msg in tests:
        assert logger_msg_formatter(fmt, d) == msg, fmt

    # Now tests with entirely invalid formats, so warnings should be issued.
    tests = [
        # We only have two args, so a reference to a third should fail.
        '{2}',
        '%(2)s',
        # Unknown key
        '{def}',
        '%(def)s',
        # Malformed key
        '{2',
        '{',
        '2}',
        '}',
        '{}{}{}',
        '%d',
    ]

    for fmt in tests:
        with pytest.warns(UserWarning):
            assert logger_msg_formatter(fmt, d) == fmt
