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
    grav_mail = GravWaveParseEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword', alert_pocs=False)
    return grav_mail


@pytest.fixture
def supernov_email():
    supernov_email = SupernovaParseEmail(
        'imap.gmail.com',
        'email.parser.test.acc@gmail.com',
        'apassword',
        alert_pocs=False)
    return supernov_email


@pytest.fixture
def grb_email():
    grb_email = GRBParseEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword', alert_pocs=False)
    return grb_email


def test_valid_login(mail):

    foo = False
    try:
        mail = ParseEmail('imap.gmail.com', 'email.parser.test.acc@gmail.com', 'apassword')
        foo = True
    except Exception as e:
        foo = False
    assert foo


def test_invalid_login(mail):

    foo = True
    try:
        mail = ParseEmail('imap.gmail.com', 'notanaddress@gmail.com', 'notapassword')
        foo = True
    except Exception as e:
        foo = False
    assert not foo


@pytest.mark.xfail(reason="Known bug, issue #37")
def test_get_email(mail):

    read, email, exit_after_parse = mail.get_email('LVC_TEST', mark_as_read=False)

    assert read


def test_mark_as_seen():
    pass


@pytest.mark.xfail(reason="Known bug, issue #37")
def test_supernova_email(supernov_email):

    read, email, exit_after_parse = supernov_email.get_email('Supernova', mark_as_read=False)

    message = supernov_email.read_email(email)

    assert len(message) > 0

    targets = supernov_email.parse_event(email)

    assert len(targets) > 0


@pytest.mark.xfail(reason="Known bug, issue #37")
def test_grb_email(grb_email):

    read, email, exit_after_parse = grb_email.get_email('GRB', mark_as_read=False)

    message = grb_email.read_email(email)

    assert len(message) > 0

    targets = grb_email.parse_event(email)

    assert len(targets) > 0


@pytest.mark.xfail(reason="Known bug, issue #37")
def test_grav_wave_email(configname):

    selection_criteria = {'name': '5_tiles', 'max_tiles': 5}

    grav_mail = GravWaveParseEmail(
        'imap.gmail.com',
        'email.parser.test.acc@gmail.com',
        'apassword',
        configname=configname,
        alert_pocs=False,
        selection_criteria=selection_criteria,
        test_message=True)

    read, email, exit_after_parse = grav_mail.get_email('LVC_TEST', mark_as_read=False)
    message = grav_mail.read_email(email)

    assert len(message) > 0

    targets = grav_mail.parse_event(email)

    assert len(targets) == 5
