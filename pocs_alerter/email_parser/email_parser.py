#!/usr/bin/env python
import imaplib
import datetime
import email
import imaplib
import mailbox
import astropy.units as u

from pocs_alerter.grav_wave.grav_wave import GravityWaveEvent
from pocs.utils.config import load_config

class ParseEmail():

    def __init__(self, host, address, password, test=False, configname='', alert_pocs=True, *args, **kwargs):

        if configname == '':
            self.config = load_config('config')
        else:
            try:
                self.config = load_config(configname)
            except:
                self.config = load_config('config')

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

        self.alert_pocs = alert_pocs

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

    def is_test_file(self, testing):

        tst = True
        type_of_tst = ''
        if 'G' in testing:
            tst = False
        else:
            tst = True
            if 'M' in testing:
                type_of_tst = 'M'
            elif 'T' in testing:
                type_of_tst = 'T'

        return tst, type_of_tst

    def read_email():
        raise NotImplementedError

    def parse_event():
        raise NotImplementedError


class ParseGravWaveEmail(ParseEmail):

    def __init__(self, host, address, password, test=False, alert_pocs=True, observer='', altitude='',
                 selection_criteria={'name': 'observable_tonight', 'max_tiles': 100}, fov={}, *args, **kwargs):

        super().__init__(host, address, password, test=test, alert_pocs=alert_pocs)

        if observer == '':

            longitude = self.config['location']['longitude'] * u.deg
            latitude = self.config['location']['latitude'] * u.deg
            elevation = self.config['location']['elevation'] * u.m
            name = self.config['location']['name']
            timezone = self.config['location']['timezone']

            self.observer = Observer(longitude=longitude, latitude=latitude, elevation=elevation, name=name, timezone=timezone)
        else:
            self.observer = observer

        if len(fov) > 0:
            self.fov = fov
        else:
            self.fov = self.config['grav_wave']['fov']

        self.selection_criteria = selection_criteria

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

    def parse_event(self, text):

        message = self.read_email(text)

        try:
            type_of_notice = message['NOTICE_TYPE']

            if 'Initial' in type_of_notice:
                type_of_notice = 'Initial'
            elif 'Update' in type_of_notice:
                type_of_notice = 'Update'
            elif 'Retraction' in type_of_notice:
                type_of_notice = 'Retraction'
        except:
            type_of_notice = ''

        message['type'] = type_of_notice

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

            grav_wave = GravityWaveEvent(fits_file, time=time,
                                         dist_cut=dist,
                                         selection_criteria=self.selection_criteria,
                                         alert_pocs=self.alert_pocs, fov=self.fov,
                                         evt_attribs=message,
                                         observer=self.observer)

            self.checked_targets = grav_wave.tile_sky()
