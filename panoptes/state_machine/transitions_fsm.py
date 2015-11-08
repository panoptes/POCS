import os
import yaml
import time
import datetime
import transitions

from ..utils.logger import has_logger
from ..utils.database import PanMongo
from ..utils.modules import load_module
from ..utils import error, listify


@has_logger
class PanStateMachine(transitions.Machine):

    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit. The state machine works in the following
    way with PANOPTES::

            * The machine consists of `states` and `transitions`.
    """

    def __init__(self, *args, **kwargs):
        assert 'states' in kwargs, self.logger.warning('states keyword required.')
        assert 'transitions' in kwargs, self.logger.warning('transitions keyword required.')

        self._loop_delay = kwargs.get('loop_delay', 5)  # seconds

        self.db = PanMongo()
        try:
            self.state_information = self.db.state_information
        except AttributeError as err:
            raise error.MongoCollectionNotFound(
                msg="Can't connect to mongo instance for states information table. {}".format(err))

        # Beginning states
        self._initial = kwargs.get('initial', 'parked')
        self._next_state = kwargs.get('first_state', 'parked')
        self._prev_state = None
        self._state_stats = dict()

        self._transitions = kwargs['transitions']
        self._states = kwargs['states']

        self.transitions = [self._load_transition(transition) for transition in self._transitions]
        self.states = [self._load_state(state) for state in self._states]

        super().__init__(
            states=self.states,
            transitions=self.transitions,
            initial=self._initial,
            send_event=True,
            before_state_change='enter_state',
            after_state_change='exit_state'
        )

        self.logger.info("State machine created")

##################################################################################################
# Properties
##################################################################################################

    @property
    def next_state(self):
        """ str: name of next state in state machine """
        return self._next_state

    @next_state.setter
    def next_state(self, next_state):
        self._next_state = next_state

    @property
    def prev_state(self):
        """ str: name of prev state in state machine """
        return self._prev_state

    @prev_state.setter
    def prev_state(self, prev_state):
        self._prev_state = prev_state

##################################################################################################
# Methods
##################################################################################################

    def run(self):
        """ Runs the state machine

        Keeps the machine in a loop until the _next_state is set as 'exit'. If the
        _prev_state is the same as the _next_state, loop without doing anything.
        """

        # Loop until we receive exit.
        while self.next_state != 'exit':
            # Don't call same state over and over
            if self.next_state != self.prev_state:
                next_state = self.next_state
                to_next_state = "to_{}".format(next_state)

                # If we can call the method
                if hasattr(self, to_next_state):
                    # Call it, otherwise exit loop
                    try:
                        getattr(self, to_next_state)()
                    except TypeError:
                        self.logger.warning("Can't go to next state, parking")
                        self.next_state = 'parking'

                    # Update the previous state
                    self.prev_state = next_state
            else:
                self.logger.info("Still in {} state".format(self._next_state))
                self.logger.info("Sleeping state machine for {} seconds".format(self._loop_delay))
                time.sleep(self._loop_delay)

        self.logger.info('Next state set to exit, leaving loop')

##################################################################################################
# Callback Methods
##################################################################################################

    def enter_state(self, event_data):
        """ Called before each state.

        Starts collecting stats on this particular state, which are saved during
        the call to `exit_state`.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
         """
        # self.logger.debug("Before going {} from {}".format(event_data.state.name, event_data.event.name))

        self._state_stats = dict()
        self._state_stats['state'] = event_data.state.name
        self._state_stats['from'] = event_data.event.name.replace('to_', '')
        self._state_stats['start_time'] = datetime.datetime.utcnow()

    def exit_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """
        # self.logger.debug("After going {} from {}".format(event_data.event.name, event_data.state.name))

        self._state_stats['stop_time'] = datetime.datetime.utcnow()
        self.state_information.insert(self._state_stats)

    def execute(self, event_data):
        """ Executes the main data for the state.

        After executing main function, check return state for validitiy. If 'exit'
        state is received for `next_state`, begin to exit system.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event.

        Note:
            This method doesn't return anything but does set the `next_state` and `prev_state` properties.
        """
        self.logger.debug("Inside {} state".format(event_data.state.name))

        # Default next state
        next_state_name = 'parking'

        # Run the `main` method for the state. Every state is required to implement this method.
        try:
            next_state_name = event_data.state.main()
        except AssertionError as err:
            self.logger.warning("Make sure the mount is initialized: {}".format(err))
        except Exception as e:
            self.logger.warning(
                "Problem calling `main` for state {}: {}".format(event_data.state.name, e))

        if next_state_name in self._states:
            self.logger.debug("{} returned {}".format(event_data.state.name, next_state_name))
            self.next_state = next_state_name
            self.prev_state = event_data.state.name

        if next_state_name == 'exit':
            self.logger.warning("Received exit signal")
            self.next_state = next_state_name
            self.prev_state = event_data.state.name

        self.logger.info("Next state is: {}".format(self.next_state))


##################################################################################################
# Class Methods
##################################################################################################

    @classmethod
    def load_state_table(cls, state_table_name='simple_state_table'):
        """ Loads the state table

        Args:
            state_table_name(str):  Name of state table. Corresponds to file name in
                `$POCS/resources/state_table/` directory. Default 'simple_state_table'.

        Returns:
            dict:                   Dictonary with `states` and `transitions` keys.
        """

        state_table_file = "{}/resources/state_table/{}.yaml".format(
            os.getenv('POCS', default='/var/panoptes/POCS'), state_table_name)

        state_table = {'states': [], 'transitions': []}

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {} {}'.format(err, state_table_file))
        except:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {}'.format(state_table_file))

        return state_table

##################################################################################################
# Private Methods
##################################################################################################

    def _load_state(self, state):
        self.logger.debug("Loading {} state".format(state))
        state_module = load_module('panoptes.state_machine.states.{}'.format(state))

        return state_module.State(name=state, panoptes=self)

    def _load_transition(self, transition):
        self.logger.debug("Loading transition: {}".format(transition))

        # Make sure the transition has the weather_is_safe condition on it
        conditions = listify(transition.get('conditions', []))

        conditions.append('weather_is_safe')
        transition['conditions'] = conditions

        self.logger.debug("Returning transition: {}".format(transition))
        return transition
