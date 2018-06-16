import tweepy

from pocs.utils.logger import get_root_logger


class SocialTwitter(object):

    """Messaging class to output to Twitter
    """
    logger = get_root_logger()

    def __init__(self, consumer_key, consumer_secret, access_token, access_token_secret, output_timestamp):
        # Create a new twitter api object
        try:
            auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
            auth.set_access_token(access_token, access_token_secret)

            self.api = tweepy.API(auth)
            self.output_timestamp = output_timestamp
        except tweepy.TweepError as e:
            self.logger.warning('Error connecting to Twitter. Err: {} - Message: {}'.format(e.args[0][0]['code'], e.args[0][0]['message']))

    def send_message(self, msg, timestamp):
        try:
            if self.output_timestamp:
                retStatus = self.api.update_status('{} - {}'.format(timestamp, msg))
            else:
                retStatus = self.api.update_status(msg)
        except tweepy.TweepError as e:
            self.logger.debug('Error tweeting message. Please check your Twitter configuration.')
