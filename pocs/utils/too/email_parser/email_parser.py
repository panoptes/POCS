#!/usr/bin/env python
import imaplib
import datetime
import email
import imaplib
import mailbox
import astropy.units as u
from astroplan import Observer
from warnings import warn

from pocs.utils.too.alert_pocs import Alerter
from pocs.utils.too.grav_wave.grav_wave import GravityWaveEvent
from pocs.utils.config import load_config
from astropy.time import Time
from astropy.coordinates import SkyCoord


class ParseEmail(object):

    '''Creates email parser classes for Gravity Wave events, Supernoave and Gamma Ray Bursts.
    They look for emails, read them and create a dictionary with their parameters to which is
    used to create new targets for observation.'''

    def __init__(
            self,
            host,
            address,
            password,
            test_message=False,
            configname='email_parsers',
            alert_pocs=True,
            *args,
            **kwargs):

        self.configname = configname

        self.config = load_config(configname)

        self.verbose = kwargs.get('verbose', False)

        self.imap_host = host
        self.imap_user = address
        self.imap_pass = password
        self.test_message = test_message
        self.checked_targets = []
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_host)
        except Exception as e:
            if self.verbose:
                warn('Bad host!')
            raise e
        try:
            self.mail.login(self.imap_user, self.imap_pass)
        except Exception as e:
            if self.verbose:
                warn('Bad email address/ password!')
            raise e

        self.alert_pocs = alert_pocs

    def mark_as_read(self, data):
        '''Marks the mail as read. Will not break code if fails, but will raise warning.'''

        try:
            self.mail.store(data, '+FLAGS', '\Seen')
        except Exception as e:
            if self.verbose:
                warn('Could not mark as seen!')

    def get_email(self, subject, folder='inbox'):
        '''Gets the email  of given subject and convert it into a string.
        If the email cannot be read, it returns read = False and and empty string.'''

        text = ''
        read = False

        folderStatus, UnseenInfo = self.mail.status('INBOX', "(UNSEEN)")
        self.mail.select(folder)  # connect to inbox.
        try:
            result, data = self.mail.search(None, '(SUBJECT "' + subject + '")')

            data = data[0].split()

            try:
                self.mark_as_read(data[-1])
            except Exception as e:
                warn('Could not mark as seen!')

            ids = data[-1]  # data is a list. We get the last email
            id_list = ids.split()  # ids is a space separated string
            latest_email_id = id_list[-1]  # get the latest

            # fetch the email body (RFC822) for the given ID
            result, data = self.mail.fetch(latest_email_id, "(RFC822)")

            raw_email = data[0][1]  # gets the text of the last email
            raw_email_string = raw_email.decode('utf-8')  # decodes
            email_message = email.message_from_string(raw_email_string)

            date_tuple = email.utils.parsedate_tz(email_message['Date'])
            if self.verbose:
                if date_tuple:
                    local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    local_message_date = "%s" % (str(local_date.strftime("%a, %d %b %Y %H:%M:%S")))
                    print(local_message_date)

            for part in email_message.walk():  # converts to actual string format
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    text = body.decode('utf-8')
                    read = True
                else:
                    continue

        except Exception as e:
            if self.verbose:
                warn('Could not get email!')

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

    def read_email(self):
        raise NotImplementedError

    def parse_event(self):
        raise NotImplementedError


class GravWaveParseEmail(ParseEmail):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def read_email(self, text):
        '''Formats the string file into a python dictionary containing all the event attributes.'''

        text.replace('\r', '')  # get rid of formatting markers in the string
        split_msg = text.split('\n')  # split message at each line
        # this will be a dictionary with Key: Value corresponding to Some_Attribute:     Its Value in the email.
        more_split_msg = {}
        for msg in split_msg:

            msg.replace('\r', '')  # gets rid of more formatting
            items = msg.split(' ', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(items) > 1:  # only keep lines that have values
                items[0] = items[0].replace(':', '')  # some more formatting removal
                items2 = items[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[items[0]] = items2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):
        '''After read_email returns the python dictionary, this method craetes all the parameters
        to pass to GravityWaveEvent, which then handles the target creation.'''

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
        except Exception as e:
            type_of_notice = ''
            if self.verbose:
                warn('Could not find type of notice!')

        message['type'] = type_of_notice

        try:
            fits_file = message['SKYMAP_URL']
        except Exception as e:
            try:
                fits_file = message['SKYMAP_BASIC_URL']
            except Exception as e:
                if self.verbose:
                    warn('ERROR: fits file not found! Cannot parse event!')
                raise e
        try:

            testing, type_of_testing = self.is_test_file(message['TRIGGER_NUM'])
        except Exception as e:
            testing = True
            type_of_testing = 'some_other'
            if self.verbose:
                warn('Could not find type of testing!')
        try:
            ti = message['TRIGGER_TIME:'].split('{', 1)
            [tim, form] = ti[0].split('S')
            form = 'S' + form
            time = Time(float(tim), format='jd', scale='utc')
        except Exception as e:
            time = Time(0.0, format='jd', scale='utc')
            if self.verbose:
                warn('Could not find start time!')
        try:
            dist = float(message['MAX_DIST'].split('[')[0])
        except Exception as e:
            dist = 50.0
            if self.verbose:
                warn('Could not find maximum distance!')

        if testing == self.test_message:

            grav_wave = GravityWaveEvent(fits_file, time=time,
                                         dist_cut=dist,
                                         alert_pocs=self.alert_pocs,
                                         configname=self.configname,
                                         evt_attribs=message,
                                         verbose=self.verbose)

            targets = grav_wave.tile_sky()
        self.checked_targets = targets
        return targets


class SupernovaParseEmail(ParseEmail):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def get_target_properties(self, message):

        name = message['NAME']
        coords = SkyCoord(float(message['RA']), float(message['DEC']), frame=message['FRAME'], unit=message['UNIT'])

        target = {'name': name,
                  'position': str(coords.to_string('hmsdms')),
                  'priority': 200,
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
            items = msg.split(':', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(items) > 1:  # only keep lines that have values
                items2 = items[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[items[0]] = items2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):

        message = self.read_email(text)
        targets = []

        try:
            targets = [self.get_target_properties(message)]
        except:
            if self.verbose:
                warn('Could not find targets!')

        if self.alert_pocs:
            alerter = Alerter(verbose=self.verbose)

            alerter.send_alert(True, message['TYPE'], targets)
        self.checked_targets = targets

        return targets


class GRBParseEmail(ParseEmail):

    def __init__(self, host, address, password, test_message=False, alert_pocs=True, configname='',
                 *args, **kwargs):

        super().__init__(host, address, password, test_message=test_message,
                         alert_pocs=alert_pocs, configname=configname, *args, **kwargs)
        self.verbose = kwargs.get('verbose', False)

    def get_target_properties(self, message):

        name = message['NAME']
        coords = SkyCoord(float(message['RA']), float(message['DEC']), frame=message['FRAME'], unit=message['UNIT'])

        target = {'name': name,
                  'position': str(coords.to_string('hmsdms')),
                  'priority': 200,
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
            items = msg.split(':', 1)  # splits each line so that thing[0] is the key and thing[1] the value
            if len(items) > 1:  # only keep lines that have values
                items2 = items[1].split('\r')  # even more formatting removal (trust me, you need these)
                more_split_msg[items[0]] = items2[0].replace(' ', '')  # gets rid of white spaces.

        return more_split_msg

    def parse_event(self, text):

        message = self.read_email(text)
        targets = []

        try:
            targets = [self.get_target_properties(message)]
        except Exception as e:
            if self.verbose:
                warn('Could not find targets!')

        if self.alert_pocs:
            alerter = Alerter(verbose=self.verbose)

            alerter.send_alert(True, message['TYPE'], targets)

        self.checked_targets = targets

        return targets
