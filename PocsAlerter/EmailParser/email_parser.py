#!/usr/bin/env python
import imaplib
import datetime
import email
import imaplib
import mailbox

from alert_pocs import AlertPocs
from horizon_range import Horizon
from grav_wave import GravityWaveEvent

class ParseEmail():

    def __init__(self, host, address, password, ):

        self.imap_host = host
        self.imap_user = address
        self.imap_pass = password

        self.mail = imaplib.IMAP4_SSL(self.imap_host)

        self.mail.login(self.imap_user, self.imap_pass)
