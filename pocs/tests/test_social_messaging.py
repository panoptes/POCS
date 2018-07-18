import pytest
import tweepy
import requests
import unittest.mock

from pocs.utils.social_twitter import SocialTwitter
from pocs.utils.social_slack import SocialSlack


@pytest.fixture(scope='module')
def twitter_config():
    twitter_config = {'consumer_key': 'mock_consumer_key', 'consumer_secret': 'mock_consumer_secret', 'access_token': 'mock_access_token', 'access_token_secret': 'access_token_secret'}
    return twitter_config


@pytest.fixture(scope='module')
def slack_config():
    slack_config = {'webhook_url': 'mock_webhook_url', 'output_timestamp': False}
    return slack_config


# Twitter sink tests
def test_no_consumer_key(twitter_config):
    with unittest.mock.patch.dict(twitter_config), pytest.raises(ValueError) as ve:
        del twitter_config['consumer_key']
        social_twitter = SocialTwitter(**twitter_config)
        assert 'consumer_key parameter is not defined.' == str(ve.value)


def test_no_consumer_secret(twitter_config):
    with unittest.mock.patch.dict(twitter_config), pytest.raises(ValueError) as ve:
        del twitter_config['consumer_secret']
        social_twitter = SocialTwitter(**twitter_config)
        assert 'consumer_secret parameter is not defined.' == str(ve.value)


def test_no_access_token(twitter_config):
    with unittest.mock.patch.dict(twitter_config), pytest.raises(ValueError) as ve:
        del twitter_config['access_token']
        social_twitter = SocialTwitter(**twitter_config)
        assert 'access_token parameter is not defined.' == str(ve.value)


def test_no_access_token_secret(twitter_config):
    with unittest.mock.patch.dict(twitter_config), pytest.raises(ValueError) as ve:
        del twitter_config['access_token_secret']
        social_twitter = SocialTwitter(**twitter_config)
        assert 'access_token_secret parameter is not defined.' == str(ve.value)


def test_send_message_twitter(twitter_config):
    with unittest.mock.patch.object(tweepy.API, 'update_status') as mock_update_status:
        social_twitter = SocialTwitter(**twitter_config)
        mock_message = "mock_message"
        mock_timestamp = "mock_timestamp"
        social_twitter.send_message(mock_message, mock_timestamp)

        mock_update_status.assert_called_once_with('{} - {}'.format(mock_message, mock_timestamp))


def test_send_message_twitter_no_timestamp(twitter_config):
    with unittest.mock.patch.dict(twitter_config, {'output_timestamp': False}), unittest.mock.patch.object(tweepy.API, 'update_status') as mock_update_status:
        social_twitter = SocialTwitter(**twitter_config)
        mock_message = "mock_message"
        mock_timestamp = "mock_timestamp"
        social_twitter.send_message(mock_message, mock_timestamp)

        mock_update_status.assert_called_once_with(mock_message)


# Slack sink tests
def test_no_webhook_url(slack_config):
    with unittest.mock.patch.dict(slack_config), pytest.raises(ValueError) as ve:
        del slack_config['webhook_url']
        slack_config = SocialSlack(**slack_config)
        assert 'webhook_url parameter is not defined.' == str(ve.value)


def test_send_message_slack(slack_config):
    with unittest.mock.patch.object(requests, 'post') as mock_post:
        social_slack = SocialSlack(**slack_config)
        mock_message = "mock_message"
        mock_timestamp = "mock_timestamp"
        social_slack.send_message(mock_message, mock_timestamp)

        mock_post.assert_called_once_with(slack_config['webhook_url'], json={'text': mock_message})


def test_send_message_slack_timestamp(slack_config):
    with unittest.mock.patch.dict(slack_config, {'output_timestamp': True}), unittest.mock.patch.object(requests, 'post') as mock_post:
        social_slack = SocialSlack(**slack_config)
        mock_message = "mock_message"
        mock_timestamp = "mock_timestamp"
        social_slack.send_message(mock_message, mock_timestamp)

        mock_post.assert_called_once_with(slack_config['webhook_url'], json={'text': '{} - {}'.format(mock_message, mock_timestamp)})
