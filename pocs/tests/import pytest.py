import pytest
from pocs_alerter.alert_pocs import AlertPocs

@pytest.fixture
def token_message():

	message = [{'coords': '0h0m0s 0d0m0s', 'name': 'Not an actual target',
			   'priority': 0, 'exp_time': 0}]

def test_send_add_target_message(token_message):

	alerter = alert_pocs.AlertPocs()

	alerter.alert_pocs(True, 'add', token_message)

