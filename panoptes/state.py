"""
.. module:: state
    :synoposis: Represents a valid `State`

"""

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class StateMachine(object):
    def __init__(self, observatory, state_table):
        """
        Initialize the StateMachine with an `Observatory` and a `StateTable`. Loads instances
        of the state into the `states` dict. Sets `current_state` to 'shutdown'
        """
        self.observatory = observatory
        self.state_table = state_table

        # Create our conditions that operate on our observatory
        self.conditions = Conditions(self.observatory)

        # Each key in the state_table is a State
        # so we load instances of all possible States into
        # a lookup dict
        self.states = self._load_states()

        # Always start from shutdown
        self.current_state = 'shutdown'


    def run(self):  
        """
        Begins a run through the state machine
        """
        # Loop until manual break
        while True:
            # Get an instance of the current State
            state = self.get_current_state()

            # Execute the action for the current State
            state.execute()

            # Perform a Conditions check, which tests ALL Conditions, setting
            # each condition property to True/False
            self.conditions.check()
            
            # Lookup required conditions for current_state. This returns an
            # iterable collection of conditions and the next_state
            state_conditions = self.get_required_conditions()
            
            # If all required conditions are true
            if state_conditions.all():
                self.current_state = self.get_next_state()                


    def get_current_state(self):
        """ 
        Returns an instance of the current State. Defaults to the `self.failsafe_state` if lookup is
        not successful.
        """
        return self.states.get(self.current_state, self.failsafe_state)


    def failsafe_state(self):
        """
        This is used in case a state can't be found. TODO: Guarantee failsafe_state is loaded.
        """
        return self.states.get('parking')        


    def _load_states(self):
        """ 
        Loops through the keys of the `StateTable` and loads instances of each `State`.
        """


@logger.has_logger
class Conditions(object):
    def __init__(self, observatory, required_conditions):
        self.observatory = observatory
        self.required_conditions = required_conditions


    def check(self):
        """ 
        Iterates through the  `required_conditions` for the current 
        `State`
        """
        pass

    def get_required_conditions(self):
        """ """
        pass