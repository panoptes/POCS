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
        self.conditions = Conditions(self.observatory, self.state_table)

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
        assert self.state_table, self.logger.warn('No state table provided')

class State(object):
    """
    Our actual `State` object. Contains an instance of the `Observatory` class as well
    as the `next_state`. Our `State` will be `execute`d by the `StateMachine`. There are
    also `before` and `after` methods that can be overridden to prepare/cleanup the
    `Observatory`.
    """
    def __init__(self,observatory, current_state, next_state='Parked'):
        self.observatory = observatory
        self.current_state = current_state
        self.next_state = next_state


    def _execute(self, payload=None):
        """
        This is a private method and is responsible for calling `before` and `after` before the
        overridden `execute` method is called.
        """
        self.before(payload)
        self.execute(payload)
        self.after(payload)


    def execute(self, payload=None):
        """
        Overridden method that will contain the actual `State` logic. An optional `payload` may
        be passed along with the `State`.
        """
        raise NotImplementedError()

    def after(self, payload=None):
        """
        Called after `execute`
        """
        raise NotImplementedError()

    def before(self, payload=None):
        """
        Called before `execute`
        """
        raise NotImplementedError()

    @property
    def next_state(self):
        """
        Returns the instance of the `next_state`.
        """
        return self.__next_state

    @next_state.setter
    def next_state(self, state_name):
        self.__next_state = State(self.observatory, state_name, )


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