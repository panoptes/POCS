#!/usr/bin/env python
import imaplib
import datetime
import email
import imaplib
import mailbox
import astropy.units as u

from pocs_alerter.alert_pocs import AlertPocs
from pocs_alerter.horizon.horizon_range import Horizon
from pocs_alerter.grav_wave.grav_wave import GravityWaveEvent
from pocs_alerter.horizon.horizon_range import Horizon


class ParseEmail():

    def __init__(self, host, address, password, test=False, rescan_interval=2.0,
                 types_noticed=['GCN/LVC_INITIAL', 'GCN/LVC_UPDATE'],
                 selection_criteria={'name': 'observable_tonight', 'max_tiles': 100}):

        self.imap_host = host
        self.imap_user = address
        self.imap_pass = password
        self.test = test
        self.checked_targets = []
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_host)
        except Exception as e:
            print('Bad host, ', e)
            raise e
        try:
            self.mail.login(self.imap_user, self.imap_pass)
        except Exception as e:
            print('Bad email address/ password, ', e)
            raise e

        self.types_noticed = types_noticed

        if test is True:
            self.types_noticed.append('GCN/LVC_TEST')
        self.selection_criteria = selection_criteria

    def mark_as_read(self, data):

        self.mail.store(data[-1], '+FLAGS', '\Seen')

    def get_email(self, typ, folder='inbox'):

        text = ''
        read = False

        folderStatus, UnseenInfo = self.mail.status('INBOX', "(UNSEEN)")
        self.mail.select(folder)  # connect to inbox.
        result, data = self.mail.search(None, '(SUBJECT "' + typ + '")')
        data = data[0].split()

        self.mark_as_read(data)  # <- does not work currently

        ids = data[-1]  # data is a list.
        id_list = ids.split()  # ids is a space separated string
        latest_email_id = id_list[-1]  # get the latest

        result, data = self.mail.fetch(latest_email_id, "(RFC822)")  # fetch the email body (RFC822) for the given ID

        raw_email = data[0][1]
        raw_email_string = raw_email.decode('utf-8')
        email_message = email.message_from_string(raw_email_string)

        date_tuple = email.utils.parsedate_tz(email_message['Date'])
        if date_tuple:
            local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
            local_message_date = "%s" % (str(local_date.strftime("%a, %d %b %Y %H:%M:%S")))
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
                thing[0] = thing[0].replace(':', '')
                thing2 = thing[1].split('\r')
                more_split_msg[thing[0]] = thing2[0].replace(' ', '')

        return more_split_msg

    def is_test_file(self, testing):

        tst = True
        typ_of_tst = ''
        if 'G' in testing:
            tst = False
        else:
            tst = True
            if 'M' in testing:
                typ_of_tst = 'M'
            elif 'T' in testing:
                typ_of_tst = 'T'

        return tst, typ_of_tst

    def parse_event(self, message):

        try:
            typ = message['NOTICE_TYPE']

            if 'Initial' in typ:
                typ = 'Initial'
            elif 'Update' in typ:
                typ = 'Update'
            elif 'Retraction' in typ:
                typ = 'Retraction'
        except:
            typ = ''

        message['type'] = typ

        try:
            fits_file = message['SKYMAP_URL']
        except:
            try:
                fits_file = message['SKYMAP_BASIC_URL']
            except:
                print('ERROR: fits file not found! Cannot parse event!')

        testing, type_of_testing = self.is_test_file(message['TRIGGER_NUM'])

        try:
            ti = message['TRIGGER_TIME:'].split('{', 1)
            [tim, form] = ti[0].split('S')
            form = 'S' + form
            trig_time = Time(float(tim), format='jd', scale='utc')
        except:
            time = 0
        try:
            dist = float(message['MAX_DIST'].split('[')[0])
        except:
            dist = 50.0

        if testing == self.test:

            if self.test:
                self.selection_criteria = {'name': '16 tiles', 'max_tiles': 100}

            grav_wave = GravityWaveEvent(fits_file, time=time,
                                         dist_cut=dist,
                                         selection_criteria=self.selection_criteria,
                                         alert_pocs=False, fov={'ra': 3.0, 'dec': 2.0},
                                         evt_attribs=message)

            self.checked_targets = grav_wave.tile_sky()
