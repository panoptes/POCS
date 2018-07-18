import requests

from pocs.utils.logger import get_root_logger


class SocialSlack(object):

    """Social Messaging sink to output to Slack."""

    logger = get_root_logger()

    def __init__(self, **kwargs):
        self.web_hook = kwargs.get('webhook_url', '')
        if self.web_hook == '':
            raise ValueError('webhook_url parameter is not defined.')
        else:
            self.output_timestamp = kwargs.get('output_timestamp', False)

    def send_message(self, msg, timestamp):
        try:
            if self.output_timestamp:
                post_msg = '{} - {}'.format(msg, timestamp)
            else:
                post_msg = msg

            response = requests.post(self.web_hook, json={'text': post_msg})
        except Exception as e:
            self.logger.debug('Error posting to slack: {}'.format(e))
