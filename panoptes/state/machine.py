import os
import yaml

from transitions import State
from transitions.extensions import MachineGraphSupport

from ..utils.database import PanMongo
from ..utils import error, listify
from ..utils import modules


class PanStateMachine(MachineGraphSupport):

    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit. The state machine works in the following
    way with PANOPTES::

            * The machine consists of `states` and `transitions`.
    """

    def __init__(self, state_machine_table, **kwargs):
        if isinstance(state_machine_table, str):
            self.logger.info("Loading state table")
            state_machine_table = PanStateMachine.load_state_table(state_table_name=state_machine_table)

        assert 'states' in state_machine_table, self.logger.warning('states keyword required.')
        assert 'transitions' in state_machine_table, self.logger.warning('transitions keyword required.')

        # Set up connection to database
        if not hasattr(self, 'db') or self.db is None:
            self.db = PanMongo()

        try:
            self.state_information = self.db.state_information
        except AttributeError as err:
            raise error.MongoCollectionNotFound(
                msg="Can't connect to mongo instance for states information table. {}".format(err))

        self._state_table_name = state_machine_table.get('name', 'default')

        # Setup Transitions
        _transitions = [self._load_transition(transition) for transition in state_machine_table['transitions']]

        states = [self._load_state(state) for state in state_machine_table.get('states', [])]

        super(PanStateMachine, self).__init__(
            states=states,
            transitions=_transitions,
            initial=state_machine_table.get('initial'),
            send_event=True,
            before_state_change='before_state',
            after_state_change='after_state',
            auto_transitions=False,
        )

        self.logger.debug("State machine created")

##################################################################################################
# Properties
##################################################################################################

##################################################################################################
# Methods
##################################################################################################

##################################################################################################
# Callback Methods
##################################################################################################

    def before_state(self, event_data):
        """ Called before each state.

        Starts collecting stats on this particular state, which are saved during
        the call to `after_state`.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
         """
        self.logger.debug("Before calling {} from {} state".format(event_data.event.name, event_data.state.name))

        # _state_stats = dict()
        # _state_stats['state'] = event_data.state.name
        # _state_stats['from'] = event_data.event.name.replace('to_', '')
        # _state_stats['start_time'] = datetime.datetime.utcnow()
        # self.state_information.insert(_state_stats)

    def after_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """
        self.logger.debug("After calling {} from {} state".format(event_data.event.name, event_data.state.name))

        # _state_stats = dict()
        # _state_stats['stop_time'] = datetime.datetime.utcnow()
        # self.state_information.insert(_state_stats)


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

    def _update_graph(self, event_data):
        model = event_data.model

        try:
            state_id = 'state_{}_{}'.format(event_data.event.name, event_data.state.name)
            fn = '/var/panoptes/images/states/{}.svg'.format(state_id)

            # Only make the file once
            if not os.path.exists(fn):
                model.graph.draw(fn, prog='dot')

            self.messaging.send_message('STATE', state_id)
        except Exception as e:
            self.logger.warning("Can't generate state graph: {}".format(e))

    def _load_state(self, state):
        self.logger.debug("Loading state: {}".format(state))
        try:
            state_module = modules.load_module('panoptes.state.states.{}.{}'.format(self._state_table_name, state))
            s = None

            # Get the `on_enter` method
            self.logger.debug("Checking {}".format(state_module))
            if hasattr(state_module, 'on_enter'):
                on_enter_method = getattr(state_module, 'on_enter')
                setattr(self, 'on_enter_{}'.format(state), on_enter_method)
                self.logger.debug("Added `on_enter` method from {} {}".format(state_module, on_enter_method))

                self.logger.debug("Created state")
                s = State(name=state)

                # Draw graph
                s.add_callback('enter', '_update_graph')

                # Then do state logic
                s.add_callback('enter', 'on_enter_{}'.format(state))
        except Exception as e:
            self.logger.warning("Can't load state modules: {}\t{}".format(state, e))

        return s

    def _load_transition(self, transition):
        self.logger.debug("Loading transition: {}".format(transition))

        # Add `check_safety` as the first transition for all states
        conditions = listify(transition.get('conditions', []))

        conditions.insert(0, 'check_safety')
        transition['conditions'] = conditions

        self.logger.debug("Returning transition: {}".format(transition))
        return transition
