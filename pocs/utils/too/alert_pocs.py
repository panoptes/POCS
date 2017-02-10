#!/usr/bin/env python

# Import POCS messanger
from pocs.utils.messaging import PanMessaging as pm


class AlertPocs():

    def __init__(self, test=False, port_num=6500):
        self.sender = pm.create_publisher(port_num)
        self.test = test

################################
# Parsing and Checking Methods #
################################
##
    def alert_pocs(self, available, citation, targets):

        citation = self.get_type_of_alert(citation)
        message = ''

        if available:
            if citation == 'followup':
                message = 'modify'
            elif citation == 'retraction':
                message = 'remove'
            else:
                message = 'add'

            self.sender.send_message('schedule', {'message': message, 'targets': targets})
            print("Message sent: ", citation, " for targets: ", targets)

        else:
            print('No target(s) found, POCS not alerted.')

    def get_type_of_alert(self, alert):

        if 'Initial' in alert:
            alert = 'add'
        elif 'Retraction' in alert or 'retraction' in alert:
            alert = 'retraction'
        elif 'Update' in alert or 'Followup' in alert or 'followup' in alert:
            alert = 'followup'
        else:
            alert = ''
        return alert
