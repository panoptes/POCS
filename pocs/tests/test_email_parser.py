import pytest

from pocs_alerter.email_parser.email_parser import ParseEmail

mail = ParseEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')


def test_valid_login():

    foo = False
    try:
        mail = ParseEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
        foo = True
    except:
        foo = False
    assert foo


def test_invalid_login():

    foo = True
    try:
        mail = ParseEmail('imap.gmail.com', 'notanaddress@gmail.com', 'notapassword')
        foo = True
    except:
        foo = False
    assert foo == False


def test_get_email():

    read, email = mail.get_email('LVC_TEST')

    assert read


def test_read_email():

    read, email = mail.get_email('LVC_TEST')

    message = mail.read_email(email)

    assert len(message) > 0


def test_mark_as_seen():
    pass
