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

    def __init__(self, host, address, password, test = False, rescan_interval = 2.0 * u.minute, 
                 types_noticed = ['GCN/LVC_INITIAL', 'GCN/LVC_UPDATE', 'GCN/LVC_TEST', 'GCN/LVC_COUNTERPART'],
                 criteria_for_loop='infinite', until = ''):

        self.imap_host = host
        self.imap_user = address
        self.imap_pass = password
        self.test = test
        self.rescan_interval = rescan_interval
        self.checked_targets = []

        self.mail = imaplib.IMAP4_SSL(self.imap_host)

        self.mail.login(self.imap_user, self.imap_pass)

        self.types_noticed = types_noticed

        if 'until' in criteria_for_loop:
            self.until = until

    def mark_as_read(self, data):

        self.mail.store(data[-1],'+FLAGS','\Seen')

    def get_email(self, typ, folder = 'inbox'):

        text = ''
        read = False

        folderStatus, UnseenInfo = self.mail.status('INBOX', "(UNSEEN)")
        self.mail.select(folder) # connect to inbox.
        result, data = self.mail.search(None, '(SUBJECT "' + typ + '")')
        data = data[0].split()

        self.mark_as_read(data) #<- does not work currently

        ids = data[-1] # data is a list.
        id_list = ids.split() # ids is a space separated string
        latest_email_id = id_list[-1] # get the latest

        result, data = self.mail.fetch(latest_email_id, "(RFC822)") # fetch the email body (RFC822) for the given ID

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
            trig_time = Time(float(tim), format = 'jd', scale = 'utc')
        except:
            time = 0
        try:
            dist = float(message['MAX_DIST'].split('[')[0])
        except:
            dist = 50.0

        if testing == self.test:

            if self.test == True:
                selection_criteria = {'type': '16 tiles', 'max_tiles': 100}
            else:
                selection_criteria = {'type': 'observable_tonight', 'max_tiles': 3000},


            grav_wave = GravityWaveEvent(fits_file, time = time,
                                         dist_cut = dist, 
                                         selection_criteria = selection_criteria,
                                         alert_pocs=False, fov = {'ra': 3.0, 'dec': 2.0},
                                         evt_attribs = message)

            self.checked_targets = grav_wave.tile_sky()

    def is_criteria_met(self, time, sun_rise_set):

        criteria = False

        if self.criteria_for_loop == 'infinite':
            criteria = False
        elif self.criteria_for_loop == 'tonight':

            if time > sun_rise_set[0]:
                criteria = True

        elif 'until' in self.criteria_for_loop:

            if time > self.until:
                criteria = True

        return criteria


    def loop_over_time(self):

        horizon = Horizon()

        time = horizon.time_now()

        sun_set_rise = horizon.sun_rise_set()

        criteria = is_criteria_met(time, sun_set_rise)

        while criteria == False:

            if self.time_interval%time < 0.001:

                for typ in types_noticed:

                    read, text = self.get_email(typ, folder = 'inbox')

                    if read == True:

                        message = self.read_email(text)

                        self.parse_event(message)

            time = horizon.time_now()

            criteria = is_criteria_met(time, sun_set_rise)


if __name__ == '__main__':

    self.loop_over_time()