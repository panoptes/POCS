#!/usr/bin/env python
import imaplib
import datetime
import email
import imaplib
import mailbox
import astropy.units as u
from astroplan import Observer

from pocs.utils.too.alert_pocs import AlertPocs
from pocs.utils.too.grav_wave.grav_wave import GravityWaveEvent
from pocs.utils.config import load_config
from astropy.time import Time
from astropy.coordinates import SkyCoord


class ParseEmail():

    def __init__(self, host, address, password, test=False, configname='', alert_pocs=True, *args, **kwargs):

        self.configname = configname

        if configname == '':
            self.config = load_config(configname)
        else:
            self.config = load_config(configname)
            if len(self.config) == 0:
                self.config = load_config('email_parsers')

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

        try:
            self.mail.store(data[-1], '+FLAGS', '\Seen')
        except Exception as e:
            print('Could not mark as seen, Error: ', e)

    def get_email(self, typ, folder='inbox'):

        text = ''
        read = False

        folderStatus, UnseenInfo = self.mail.status('INBOX', "(UNSEEN)")
        self.mail.select(folder)  # connect to inbox.
        try:
            result, data = self.mail.search(None, '(SUBJECT "' + typ + '")')

            data = data[0].split()

            self.mark_as_read(data)

            ids = data[-1]  # data is a list.
            id_list = ids.split()  # ids is a space separated string
            latest_email_id = id_list[-1]  # get the latest

            # fetch the email body (RFC822) for the given ID
            result, data = self.mail.fetch(latest_email_id, "(RFC822)")

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

        except:
            return False, ''

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

    def __init__(self, host, address, password, test=False, alert_pocs=True, observer='', altitude='', configname='',
                 selection_criteria='', fov={}, *args, **kwargs):

        super().__init__(host, address, password, test=test, alert_pocs=alert_pocs, configname=configname)

    def read_email(self, text):

        text.replace('\r', '')  # get rid of formatting markers in the string
        split_msg = text.split('\n')  # split message at each line
        # this will be a dictionary with Key: Value corresponding to Some_Attribute:     Its Value in the email.
        more_split_msg = {}
        for msg in split_msg:

            msg.replace('\r', '')  # gets rid of more formatting
            thing = msg.split(' ', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(thing) > 1:  # only keep lines that have values
                thing[0] = thing[0].replace(':', '')  # some more formatting removal
                thing2 = thing[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[thing[0]] = thing2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):
        targets = []
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

        try:

            testing, type_of_testing = self.is_test_file(message['TRIGGER_NUM'])
        except:
            testing = True
            type_of_testing = 'some_other'
        try:
            ti = message['TRIGGER_TIME:'].split('{', 1)
            [tim, form] = ti[0].split('S')
            form = 'S' + form
            trig_time = Time(float(tim), format='jd', scale='utc')
        except:
            time = Time(0.0, format='jd', scale='utc')
        try:
            dist = float(message['MAX_DIST'].split('[')[0])
        except:
            dist = 50.0

        if testing == self.test:

            grav_wave = GravityWaveEvent(fits_file, time=time,
                                         dist_cut=dist,
                                         alert_pocs=self.alert_pocs,
                                         configname=self.configname,
                                         evt_attribs=message)

            targets = grav_wave.tile_sky()
        self.checked_targets = targets
        return targets


class ParseSupernovaEmail(ParseEmail):

    def __init__(self, host, address, password, test=False, alert_pocs=True, configname='',
                 *args, **kwargs):

        super().__init__(host, address, password, test=test, alert_pocs=alert_pocs, configname=configname)

    def get_target_properties(self, message):

        name = message['NAME']
        coords = SkyCoord(float(message['RA']), float(message['DEC']), frame=message['FRAME'], unit=message['UNIT'])

        target = {'name': name,
                  'position': str(coords.to_string('hmsdms')),
                  'priority': '200',
                  'exp_time': 10 * 60,
                  'min_nexp': 6,
                  'exp_set_size': 1, }

        return target

    def read_email(self, text):

        text.replace('\r', '')  # get rid of formatting markers in the string
        split_msg = text.split('\n')  # split message at each line
        # this will be a dictionary with Key: Value corresponding to Some_Attribute:     Its Value in the email.
        more_split_msg = {}
        for msg in split_msg:

            msg.replace('\r', '')  # gets rid of more formatting
            thing = msg.split(':', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(thing) > 1:  # only keep lines that have values
                thing2 = thing[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[thing[0]] = thing2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):

        message = self.read_email(text)

        try:
            targets = [self.get_target_properties(message)]
        except:
            return []

        if self.alert_pocs:
            alerter = AlertPocs()

            alerter.alert_pocs(True, message['TYPE'], targets)
        self.checked_targets = targets

        return targets


class ParseGRBEmail(ParseEmail):

    def __init__(self, host, address, password, test=False, alert_pocs=True, configname='',
                 *args, **kwargs):

        super().__init__(host, address, password, test=test, alert_pocs=alert_pocs, configname=configname)

    def get_target_properties(self, message):

        name = message['NAME']
        coords = SkyCoord(float(message['RA']), float(message['DEC']), frame=message['FRAME'], unit=message['UNIT'])

        target = {'name': name,
                  'position': str(coords.to_string('hmsdms')),
                  'priority': '200',
                  'exp_time': 10 * 60,
                  'min_nexp': 6,
                  'exp_set_size': 1, }

        return target

    def read_email(self, text):

        text.replace('\r', '')  # get rid of formatting markers in the string
        split_msg = text.split('\n')  # split message at each line
        # this will be a dictionary with Key: Value corresponding to Some_Attribute:     Its Value in the email.
        more_split_msg = {}
        for msg in split_msg:

            msg.replace('\r', '')  # gets rid of more formatting
            thing = msg.split(':', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(thing) > 1:  # only keep lines that have values
                thing2 = thing[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[thing[0]] = thing2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):

        message = self.read_email(text)

        try:
            targets = [self.get_target_properties(message)]
        except:
            return []

        if self.alert_pocs:
            alerter = AlertPocs()

            alerter.alert_pocs(True, message['TYPE'], targets)

        self.checked_targets = targets

        return targets
