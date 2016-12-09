import os
import yaml

from transitions import State

from ..utils import error
from ..utils import listify
from ..utils import load_module

can_graph = False
try:
    import pygraphviz
    from transitions.extensions import GraphMachine as Machine
    can_graph = True
except ImportError:
    from transitions import Machine


class PanStateMachine(Machine):

    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit. The state machine works in the following
    way with PANOPTES::

            * The machine consists of `states` and `transitions`.
    """

    def __init__(self, state_machine_table, **kwargs):

        if isinstance(state_machine_table, str):
            self.logger.info("Loading state table: {}".format(state_machine_table))
            state_machine_table = PanStateMachine.load_state_table(state_table_name=state_machine_table)

        assert 'states' in state_machine_table, self.logger.warning('states keyword required.')
        assert 'transitions' in state_machine_table, self.logger.warning('transitions keyword required.')

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
            name="POCS State Machine"
        )

        self._state_machine_table = state_machine_table
        self._next_state = None
        self._keep_running = False
        self._run_once = False
        self._do_states = True

        self.logger.debug("State machine created")

##################################################################################################
# Properties
##################################################################################################

    @property
    def keep_running(self):
        return self._keep_running

    @property
    def do_states(self):
        return self._do_states

    @property
    def run_once(self):
        return self._run_once

    @property
    def next_state(self):
        return self._next_state

    @next_state.setter
    def next_state(self, value):
        """ Set the tracking rate """
        self._next_state = value

##################################################################################################
# Methods
##################################################################################################

    def run(self, exit_when_done=False, run_once=False):
        """Runs the state machine loop

        This runs the state machine in a loop. Setting the machine proprety
        `is_running` to False will stop the loop.

        Args:
            exit_when_done (bool, optional): If True, the loop will exit when `do_states`
                has become False, otherwise will sleep (default)
            run_once (bool, optional): If the machine loop should only run one time, defaults
                to False to loop continuously.
        """
        assert self.is_initialized, self.logger.error("POCS not initialized")

        self._keep_running = True
        self._run_once = run_once

        # Start with `get_ready`
        self.next_state = 'ready'

        _loop_iteration = 0

        while self.keep_running:
            state_changed = False

            # If we are processing the states
            if self.do_states:
                # Get the next transition method based off `state` and `next_state`
                call_method = self._lookup_trigger()

                self.logger.debug("Transition method: {}".format(call_method))
                if call_method and hasattr(self, call_method):
                    caller = getattr(self, call_method)
                else:
                    self.logger.warning("No valid state given, parking")
                    caller = self.park

                try:
                    state_changed = caller()
                except Exception as e:
                    self.logger.warning("Problem calling next state: {}".format(e))

                # If we didn't successfully transition, sleep a while then try again
                if not state_changed:
                    if _loop_iteration > 5:
                        self.logger.warning("Stuck in current state for 5 iterations, parking")
                        self.next_state = 'parking'
                    else:
                        self.logger.warning("State transition failed. Sleeping before trying again")
                        _loop_iteration = _loop_iteration + 1
                        self.sleep(with_status=False)

                if 'all' in self.config['simulator']:
                    self.sleep(5)

            elif exit_when_done:
                break
            else:
                self.sleep(5)

    def stop_states(self):
        """ Stops the machine loop on the next iteration """
        self.logger.info("Stopping POCS states")
        self._do_states = False


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

    def after_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """

        self.logger.debug("After calling {}. Now in {} state".format(event_data.event.name, event_data.state.name))


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

    def _lookup_trigger(self):
        self.logger.debug("Source: {}\t Dest: {}".format(self.state, self.next_state))
        for state_info in self._state_machine_table['transitions']:
            if self.state in state_info['source'] and state_info['dest'] == self.next_state:
                return state_info['trigger']

        # Return parking if we don't find anything
        return 'parking'

    def _update_status(self, event_data):
        self.status()

    def _update_graph(self, event_data):  # pragma: no cover
        model = event_data.model

        try:
            state_id = 'state_{}_{}'.format(event_data.event.name, event_data.state.name)

            image_dir = self.config['directories']['images']
            os.makedirs('{}/state_images/'.format(image_dir), exist_ok=True)

            fn = '{}/state_images/{}.svg'.format(image_dir, state_id)
            ln_fn = '{}/state.svg'.format(image_dir)

            # Only make the file once
            if not os.path.exists(fn):
                model.graph.draw(fn, prog='dot')

            # Link current image
            if os.path.exists(ln_fn):
                os.remove(ln_fn)

            os.symlink(fn, ln_fn)

        except Exception as e:
            self.logger.warning("Can't generate state graph: {}".format(e))

    def _load_state(self, state):
        self.logger.debug("Loading state: {}".format(state))
        try:
            state_module = load_module('pocs.state.states.{}.{}'.format(self._state_table_name, state))
            s = None

            # Get the `on_enter` method
            self.logger.debug("Checking {}".format(state_module))
            if hasattr(state_module, 'on_enter'):
                on_enter_method = getattr(state_module, 'on_enter')
                setattr(self, 'on_enter_{}'.format(state), on_enter_method)
                self.logger.debug("Added `on_enter` method from {} {}".format(state_module, on_enter_method))

                self.logger.debug("Created state")
                s = State(name=state)

                s.add_callback('enter', '_update_status')

                if can_graph:
                    s.add_callback('enter', '_update_graph')

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
