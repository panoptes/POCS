#!/usr/bin/env python
from ...utils.messaging import PanMessaging as pm


class Alerter(object):

    def __init__(self, port_num=6500, *args, **kwargs):

        self.sender = pm.create_publisher(port_num)
        self.verbose = kwargs.get('verbose', False)

################################
# Parsing and Checking Methods #
################################
##
    def send_alert(self, available, citation, targets):

        citation = self.get_type_of_alert(citation)
        message = ''

        if available:
            if citation == 'followup':
                message = 'modify'
            elif citation == 'retraction':
                message = 'remove'
            else:
                message = 'add'

            self.sender.send_message('POCS-SCHEDULE', {'message': message, 'targets': targets})

            if self.verbose:
                print("Message sent: ", citation, " for targets: ", targets)

        else:
            print('No target(s) found, POCS not alerted.')

    def get_type_of_alert(self, alert):

        alert_lookup = {'initial': 'add',
                        'update': 'followup',
                        'retraction': 'retraction',
                        'followup': 'followup'}

        return alert_lookup.get(alert.lower(), '')
