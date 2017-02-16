#!/usr/bin/env python
from ...utils.messaging import PanMessaging as pm


class Alerter(object):

    def __init__(self, port_num=6500, *args, **kwargs):

        '''Uses PanMessaging to send a list of targets as a list of python dictionaries.

        Attributes:
            port_num = 6500 by default (int): the publisher port number.
            verbose = False by default (bool): tells the methods whether or not to print.

        TODO:
            - if the message is a retraction, it only needs to send the names of all the 
                targets that contain an event number.
            - Perhaps read the port num from a config file?'''

        self.sender = pm.create_publisher(port_num)
        self.verbose = kwargs.get('verbose', False)

################################
# Parsing and Checking Methods #
################################

    def send_alert(self, citation, targets):

        '''Sends alert with the publisher of specified port number when initiated.

        Args:
            - citation (str): can be any of "initial", "update", "followup" or "retraction".
            - targets (list of python dictionaries): The targets to be sent.'''

        citation = self.get_type_of_alert(citation)
        message = ''

        if citation == 'followup':
            message = 'modify'
        elif citation == 'retraction':
            message = 'remove'
        else:
            message = 'add'

        self.sender.send_message('POCS-SCHEDULE', {'message': message, 'targets': targets})

        if self.verbose:
            print("Message sent: " + citation + " for targets: " + targets)


    def get_type_of_alert(self, alert):

        '''Translates the type of alert into the command the reciever can understand.

        Args:
            - alert (str): can be any of "initial", "update", "followup" or "retraction".

        Returns:
            - message (str): corresponding message to input. Can be any of "add", "followup" or "retraction".'''

        alert_lookup = {'initial': 'add',
                        'update': 'followup',
                        'retraction': 'retraction',
                        'followup': 'followup'}

        return alert_lookup.get(alert.lower(), '')
