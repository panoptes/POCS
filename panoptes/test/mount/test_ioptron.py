from nose.tools import raises

import panoptes
from panoptes.mount.ioptron import Mount

class TestIOptron():

	@raises(AssertionError)
	def test_no_config(self):
		""" Mount needs a config """
		mount = Mount()