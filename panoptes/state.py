"""@package panoptes.state
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class StateMachine(object):
    def __init__(self, observatory):
        """
        Initialize the StateMachine with an `Observatory`
        of the state into the `states` dict. Sets `current_state` to 'shutdown'

        @param  observatory     An instance of panoptes.observatory.Observatory
        """
        self.logger.info("Creating state machine")

        # Create a state machine container. The only outcome for our state machine is Parked,
        # otherwise machine keeps running
        self.sm = smach.StateMachine(outcomes=['parked', 'fail'])

        # Attach the observatory to the state machine userdata
        self.sm.userdata.observatory = observatory

        # We use a common dictonary to link the observatory between states
        remapping_dict = {
            'observatory_in': 'observatory',
            'observatory_out': 'observatory'
        }

        # Open our state machine container
        with self.sm:
            # Add states to the container
            smach.StateMachine.add('PARKED', Parked(), transitions={'shutdown': 'SHUTDOWN'}, remapping=remapping_dict)

            smach.StateMachine.add('SHUTDOWN', Shutdown(), transitions={'sleeping': 'SLEEPING'}, remapping=remapping_dict)

            smach.StateMachine.add('SLEEPING', Sleeping(), transitions={'parked': 'PARKED'}, remapping=remapping_dict)


    def execute(self):
        """
        Starts the execution of our state machine
        """
        self.logger.info("Beginning execution of state machine")
        outcome = self.sm.execute()
        return outcome

@logger.has_logger
class Parked(smach.State):
    def __init__(self):
        smach.State.__init__(self, outcomes=['shutdown', 'fail'], input_keys=['observatory_in'], output_keys=['observatory_out'])
        self.counter = 0

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        self.logger.info("Looking at observatory lat: {}".format(userdata.observatory_in.site.lat))
        if self.counter < 3:
            self.counter += 1
            return 'shutdown'
        else:
            return 'fail'

@logger.has_logger
class Shutdown(smach.State):
    def __init__(self):
        smach.State.__init__(self, outcomes=['sleeping'], input_keys=['observatory_in'], output_keys=['observatory_out'])

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        return 'sleeping'

@logger.has_logger
class Sleeping(smach.State):
    def __init__(self):
        smach.State.__init__(self, outcomes=['parked'], input_keys=['observatory_in'], output_keys=['observatory_out'])

    def execute(self, userdata):
        self.logger.info("Executing {}".format(type(self).__name__))
        self.logger.info("Sleeping until night")
        return 'parked'
