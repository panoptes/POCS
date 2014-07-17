"""@package panoptes.state.statemachine
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.state.states as states

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
        self.sm = smach.StateMachine(outcomes=['parked', 'quit'])

        # Attach the observatory to the state machine userdata
        self.observatory = observatory

        # Open our state machine container
        with self.sm:
            # Add states to the container
            smach.StateMachine.add('PARKED', states.Parked(observatory=self.observatory), transitions={
                                   'shutdown': 'SHUTDOWN',
                                   'parking': 'PARKING',
                                   'ready': 'READY',
                                   'quit': 'quit',
                                   })

            smach.StateMachine.add('PARKING', states.Parking(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'parked': 'PARKED'})

            smach.StateMachine.add('SHUTDOWN', states.Shutdown(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'sleeping': 'SLEEPING'})

            smach.StateMachine.add('SLEEPING', states.Sleeping(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'ready': 'READY',
                                   })

            smach.StateMachine.add('READY', states.Ready(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'scheduling': 'SCHEDULING',
                                   })

            smach.StateMachine.add('SCHEDULING', states.Scheduling(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'slewing': 'SLEWING',
                                   })

            smach.StateMachine.add('SLEWING', states.Slewing(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   'imaging': 'IMAGING',
                                   })

            smach.StateMachine.add('IMAGING', states.Imaging(observatory=self.observatory), transitions={
                                   'parking': 'PARKING',
                                   })

    def execute(self):
        """
        Starts the execution of our state machine
        """
        self.logger.info("Beginning execution of state machine")
        outcome = self.sm.execute()
        return outcome
