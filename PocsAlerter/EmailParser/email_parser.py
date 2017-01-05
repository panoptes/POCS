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

    def __init__(self, host, address, password, test = False,
                 types_noticed = ['GCN/LVC_INITIAL', 'GCN/LVC_UPDATE', 'GCN/LVC_TEST', 'GCN/LVC_COUNTERPART']):

        self.imap_host = host
        self.imap_user = address
        self.imap_pass = password
        self.test = test

        self.mail = imaplib.IMAP4_SSL(self.imap_host)

        self.mail.login(self.imap_user, self.imap_pass)

        self.types_noticed = types_noticed

    def get_email(self, typ, folder = 'inbox'):

        text = ''
        read = False

        folderStatus, UnseenInfo = mail.status('INBOX', "(UNSEEN)")
        mail.select(folder) # connect to inbox.
        result, data = mail.search(None, '(SUBJECT "' + typ + '")')
        data = data[0].split()

        mail.store(data[0],'+FLAGS','Seen') #<- does not work currently

        ids = data[0] # data is a list.
        id_list = ids.split() # ids is a space separated string
        latest_email_id = id_list[-1] # get the latest

        result, data = mail.fetch(latest_email_id, "(RFC822)") # fetch the email body (RFC822) for the given ID

        raw_email = data[0][1]
        raw_email_string = raw_email.decode('utf-8')
        email_message = email.message_from_string(raw_email_string)

        date_tuple = email.utils.parsedate_tz(email_message['Date'])
        if date_tuple:
            local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            local_message_date = "%s" %(str(local_date.strftime("%a, %d %b %Y %H:%M:%S")))
            print(local_message_date)

        for part in email_message.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True)
                text = body.decode('utf-8')
                read = True
            else:
                continue

        return read, text

    def read_email(self, text):

        text.replace('\r', '')
        split_msg = text.split('\n')
        more_split_msg = {}
        for msg in split_msg:

            msg.replace('\r', '')
            thing = msg.split(' ', 1)
            if len(thing) > 1:
                thing[0].replace(':', '')
                thing2 = thing[1].split('\r')
                more_split_msg[thing[0]] = thing2[0].replace(' ', '')

        return more_split_msg

    def is_test_file(self, testing):

        tst = True
        typ_of_tst = ''
        if 'G' in message['TRIGGER_NUM']:
            tst = False
        else:
            tst = True
            if 'M' in message['TRIGGER_NUM']:
                typ_of_tst = 'M'
            elif 'T' in message['TRIGGER_NUM']:
                typ_of_tst = 'T'

        return tst, typ_of_tst

    def parse_event(self, message):

        try:
            fits_file = message['SKYMAP_URL']
        except:
            try:
                fits_file = message['SKYMAP_BASIC_URL']
            except:
                print('ERROR: fits file not found! Cannot parse event!')

        testing, type_of_testing = self.is_test_file(message['TRIGGER_NUM'])

        try:
            time = message['TRIGGER_TIME']
        except:
            time = 0
        try:
            dist = message['MAX_DIST']
        except:
            dist = 50.0

        if testing == self.test:

            grav_wave = GravityWaveEvent(fits_file, time = time,
                                         dist_cut = dist, 
                                         selection_criteria = {'type': 'observable_tomight', 'max_tiles': 3000},
                                         alert_pocs=True, fov = ['ra': 3.0, 'dec': 2.0], dist_cut=attribs['max_dist'],
                                         evt_attribs = message)

            checked_targets = grav_wave.tile_sky()


