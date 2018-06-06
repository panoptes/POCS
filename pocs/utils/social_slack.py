import requests

from pocs.utils import current_time
from pocs.utils.logger import get_root_logger

class SocialSlack(object):

    """Messaging class to output to Slack
    """
    logger = get_root_logger()

    def __init__(self, web_hook, output_timestamp):
        self.output_timestamp = output_timestamp
        self.web_hook = web_hook

    def send_message(self, msg, timestamp):
        try:
            if self.output_timestamp:
                post_msg = '{} - {}'.format(timestamp, msg)
            else:
                post_msg = msg

            response = requests.post(self.web_hook, json={"text": post_msg})
        except Exception as e:
            self.logger.debug("Error posting to slack: {}".format(e))