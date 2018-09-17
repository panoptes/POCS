import tweepy

from pocs.utils.logger import get_root_logger


class SocialTwitter(object):

    """Social Messaging sink to output to Twitter."""

    logger = get_root_logger()

    def __init__(self, **kwargs):
        consumer_key = kwargs.get('consumer_key', '')
        if consumer_key == '':
            raise ValueError('consumer_key parameter is not defined.')
        consumer_secret = kwargs.get('consumer_secret', '')
        if consumer_secret == '':
            raise ValueError('consumer_secret parameter is not defined.')
        access_token = kwargs.get('access_token', '')
        if access_token == '':
            raise ValueError('access_token parameter is not defined.')
        access_token_secret = kwargs.get('access_token_secret', '')
        if access_token_secret == '':
            raise ValueError('access_token_secret parameter is not defined.')

        # Output timestamp should always be True by default otherwise Twitter will reject duplicate statuses.
        self.output_timestamp = kwargs.get("output_timestamp", True)

        # Create a new twitter api object
        try:
            auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
            auth.set_access_token(access_token, access_token_secret)

            self.api = tweepy.API(auth)
        except tweepy.TweepError:
            msg = 'Error authenicating with Twitter. Please check your Twitter configuration.'
            self.logger.warning(msg)
            raise ValueError(msg)

    def send_message(self, msg, timestamp):
        try:
            # update_status returns a tweepy Status instance, but we
            # drop it on the floor because we don't have anything we
            # can do with it.
            if self.output_timestamp:
                self.api.update_status('{} - {}'.format(msg, timestamp))
            else:
                self.api.update_status(msg)
        except tweepy.TweepError:
            self.logger.debug('Error tweeting message. Please check your Twitter configuration.')
