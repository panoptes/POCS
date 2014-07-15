"""@package panoptes.state.statemachine
The StateMachine for the Panoptes Project. Inherits from smach (see ros.org).
"""
import smach

import panoptes.state.mount as mount_states

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
        self.sm.userdata.observatory = observatory

        # We use a common dictonary to link the observatory between states
        remapping_dict = {
            'observatory_in': 'observatory',
            'observatory_out': 'observatory'
        }

        # Open our state machine container
        with self.sm:
            # Add states to the container
            smach.StateMachine.add('PARKED', mount_states.Parked(), transitions={
                                   'shutdown': 'SHUTDOWN',
                                   'ready': 'READY',
                                   'quit': 'quit',
                                   }, remapping=remapping_dict)

            smach.StateMachine.add('PARKING', mount_states.Parking(), transitions={
                                   'parked': 'PARKED'}, remapping=remapping_dict)

            smach.StateMachine.add('SHUTDOWN', mount_states.Shutdown(), transitions={
                                   'sleeping': 'SLEEPING'}, remapping=remapping_dict)

            smach.StateMachine.add('SLEEPING', mount_states.Sleeping(), transitions={
                                   'parking': 'PARKING',
                                   'ready': 'READY',
                                   }, remapping=remapping_dict)

            smach.StateMachine.add('READY', mount_states.Ready(), transitions={
                                   'parking': 'PARKING',
                                   'scheduling': 'SCHEDULING',
                                   }, remapping=remapping_dict)

            smach.StateMachine.add('SCHEDULING', mount_states.Scheduling(), transitions={
                                   'parking': 'PARKING',
                                   'slewing': 'SLEWING',
                                   }, remapping=remapping_dict)

            smach.StateMachine.add('SLEWING', mount_states.Slewing(), transitions={
                                   'parking': 'PARKING',
                                   'imaging': 'IMAGING',
                                   }, remapping=remapping_dict)

            smach.StateMachine.add('IMAGING', mount_states.Imaging(), transitions={
                                   'parking': 'PARKING',
                                   }, remapping=remapping_dict)

    def execute(self):
        """
        Starts the execution of our state machine
        """
        self.logger.info("Beginning execution of state machine")
        outcome = self.sm.execute()
        return outcome
