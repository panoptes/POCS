import pytest

from pocs_alerter.email_parser.email_parser import *

@pytest.fixture
def mail():
    mail = ParseEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
    return mail

@pytest.fixture
def configname():
    return 'config_donotread_1ocal'

@pytest.fixture
def grav_mail():
    grav_mail = ParseGravWaveEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
    return grav_mail

def test_valid_login():

    foo = False
    try:
        mail = ParseEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
        foo = True
    except:
        foo = False
    assert foo

@pytest.fixture
def grav_mail():
    grav_mail = ParseGravWaveEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
    return grav_mail


def test_valid_login(mail):

    foo = False
    try:
        mail = ParseEmail('imap.gmail.com', 'bernie.telalovic@gmail.com', 'hdzlezqobwooqdqt')
        foo = True
    except:
        foo = False
    assert foo

def test_invalid_login(mail):

    foo = True
    try:
        mail = ParseEmail('imap.gmail.com', 'notanaddress@gmail.com', 'notapassword')
        foo = True
    except:
        foo = False
    assert not foo

def test_get_email(mail):

    read, email = mail.get_email('LVC_TEST')

    assert read

def test_read_email(configname):

    grav_mail = ParseGravWaveEmail(
        'imap.gmail.com',
        'bernie.telalovic@gmail.com',
        'hdzlezqobwooqdqt',
        configname=configname)

    read, email = grav_mail.get_email('LVC_TEST')
    message = grav_mail.read_email(email)

    assert len(message) > 0

def test_mark_as_seen():
    pass
