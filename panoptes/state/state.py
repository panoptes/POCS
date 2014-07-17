"""@package panoptes.state.state
The base State for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.utils.logger as logger
import panoptes.utils.error as error


@logger.has_logger
class PanoptesState(smach.State):
    def __init__(self, observatory=None):
    	"""
    	Responsible for calling the setup() method supplied by the children classes,
    	which sets the outcomes list. The 'parking' outome is appended to the list
    	of possible outcomes and set as the default.
    	"""
    	# Make sure we have our observatory
    	assert observatory is not None, self.logger.warning('State class must accept observatory')
    	self.observatory = observatory

    	self.outcomes = list()

    	# Call the setup method supplied by the state, which will chage the self.outcomes
    	self.setup()

    	# Set the default outcome to 'parking'
    	self.outcome = 'parking'

    	# Add the 'parking' outcome to every class
    	self.outcomes.append('parking')

    	# Initialize
        smach.State.__init__(self, outcomes=self.outcomes)


    def execute(self, userdata):
    	"""
    	Responsible for calling the run() method supplied by the children classes,
    	which execute the state logic code and sets the appropriate outcome for the
    	state, otherwise the default 'parking' outcome is returned.
    	"""

    	# Perform the state logic code
    	self.run()

    	return self.outcome


    def setup(self):
    	raise NotImplemented()


    def run(self):
    	raise NotImplemented()