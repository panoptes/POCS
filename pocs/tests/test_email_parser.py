import pytest

from pocs.utils.too.email_parser.email_parser import *


@pytest.fixture
def mail():
    mail = ParseEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword')
    return mail


@pytest.fixture
def configname():
    return 'email_parsers'


@pytest.fixture
def grav_mail():
    grav_mail = ParseGravWaveEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword')
    return grav_mail


@pytest.fixture
def supernov_email():
    supernov_email = ParseSupernovaEmail(
        'imap.gmail.com',
        'email.parser.test.acc@gmail.com',
        'apassword',
        alert_pocs=False)
    return supernov_email


@pytest.fixture
def grb_email():
    grb_email = ParseGRBEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword', alert_pocs=False)
    return grb_email


def test_valid_login(mail):

    foo = False
    try:
        mail = ParseEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword')
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


def test_mark_as_seen():
    pass


def test_supernova_email(supernov_email):

    read, email = supernov_email.get_email('Supernova')

    message = supernov_email.read_email(email)

    assert len(message) > 0

    targets = supernov_email.parse_event(email)

    assert len(targets) > 0


def test_grb_email(grb_email):

    read, email = grb_email.get_email('GRB')

    message = grb_email.read_email(email)

    assert len(message) > 0

    targets = grb_email.parse_event(email)

    assert len(targets) > 0


def test_grav_wave_email(configname):

    selection_criteria = {'name': '5_tiles', 'max_tiles': 5}

    grav_mail = ParseGravWaveEmail(
        'imap.gmail.com',
        'email.parser.test.acc@gmail.com',
        'apassword',
        configname=configname,
        alert_pocs=False,
        selection_criteria=selection_criteria,
        test=True)

    read, email = grav_mail.get_email('LVC_TEST')
    message = grav_mail.read_email(email)

    assert len(message) > 0

    targets = grav_mail.parse_event(email)

    assert len(targets) == 5
