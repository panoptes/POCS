import os
import yaml

from transitions import State

from pocs.utils import error
from pocs.utils import listify
from pocs.utils import load_module

can_graph = False
try:  # pragma: no cover
    import pygraphviz
    from transitions.extensions import GraphMachine as Machine
    can_graph = True
except ImportError:  # pragma: no cover
    from transitions import Machine


class PanStateMachine(Machine):

    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit.
    """

    def __init__(self, state_machine_table, **kwargs):

        if isinstance(state_machine_table, str):
            self.logger.info("Loading state table: {}".format(state_machine_table))
            state_machine_table = PanStateMachine.load_state_table(
                state_table_name=state_machine_table)

        assert 'states' in state_machine_table, self.logger.warning('states keyword required.')
        assert 'transitions' in state_machine_table, self.logger.warning(
            'transitions keyword required.')

        self._state_table_name = state_machine_table.get('name', 'default')
        self._states_location = state_machine_table.get('location', 'pocs/state/states')

        # Setup Transitions
        _transitions = [self._load_transition(transition)
                        for transition in state_machine_table['transitions']]

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
        self._run_once = kwargs.get('run_once', False)
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

        This runs the state machine in a loop. Setting the machine property
        `is_running` to False will stop the loop.

        Args:
            exit_when_done (bool, optional): If True, the loop will exit when `do_states`
                has become False, otherwise will sleep (default)
            run_once (bool, optional): If the machine loop should only run one time, defaults
                to False to loop continuously.
        """
        assert self.is_initialized, self.logger.error("POCS not initialized")

        self._keep_running = True
        self._do_states = True
        run_once = run_once or self.run_once

        # Start with `get_ready`
        self.next_state = 'ready'

        _loop_iteration = 0

        while self.keep_running and self.connected:
            state_changed = False

            self.check_messages()

            # If we are processing the states
            if self.do_states:

                # If sleeping, wait until safe (or interrupt)
                if self.state == 'sleeping':
                    if self.is_safe() is not True:
                        self.wait_until_safe()

                try:
                    state_changed = self.goto_next_state()
                except Exception as e:
                    self.logger.warning("Problem going from {} to {}, exiting loop [{!r}]".format(
                        self.state, self.next_state, e))
                    self.stop_states()
                    break

                # If we didn't successfully transition, sleep a while then try again
                if not state_changed:
                    self.logger.warning("Failed to transition from {} to {}",
                                        self.state, self.next_state)
                    if self.is_safe() is False:
                        self.logger.warning(
                            "Conditions have become unsafe; setting next state to 'parking'")
                        self.next_state = 'parking'
                    elif _loop_iteration > 5:
                        self.logger.warning("Stuck in current state for 5 iterations, parking")
                        self.next_state = 'parking'
                    else:
                        _loop_iteration = _loop_iteration + 1
                        self.logger.warning(
                            "Sleeping for a bit, then trying the transition again (loop: {})",
                            _loop_iteration)
                        self.sleep(with_status=False)
                else:
                    _loop_iteration = 0

                ########################################################
                # Note that `self.state` below has changed from above
                ########################################################

                # If we are in ready state then we are making one attempt
                if self.state == 'ready':
                    self._obs_run_retries -= 1

                if self.state == 'sleeping' and run_once:
                    self.stop_states()
            elif exit_when_done:
                break
            elif not self.interrupted:
                # Sleep for one minute (can be interrupted via `check_messages`)
                self.sleep(60)

    def goto_next_state(self):
        state_changed = False

        # Get the next transition method based off `state` and `next_state`
        call_method = self._lookup_trigger()

        self.logger.debug("Transition method: {}".format(call_method))

        caller = getattr(self, call_method, 'park')
        state_changed = caller()
        self.db.insert_current('state', {"source": self.state, "dest": self.next_state})

        return state_changed

    def stop_states(self):
        """ Stops the machine loop on the next iteration """
        self.logger.info("Stopping POCS states")
        self._do_states = False

    def status(self):
        """Computes status, a dict, of whole observatory."""
        return NotImplemented

##################################################################################################
# State Conditions
##################################################################################################

    def check_safety(self, event_data=None):
        """ Checks the safety flag of the system to determine if safe.

        This will check the weather station as well as various other environmental
        aspects of the system in order to determine if conditions are safe for operation.

        Note:
            This condition is called by the state machine during each transition

        Args:
            event_data(transitions.EventData): carries information about the event if
            called from the state machine.

        Returns:
            bool:   Latest safety flag
        """

        self.logger.debug("Checking safety for {}".format(event_data.event.name))

        # It's always safe to be in some states
        if event_data and event_data.event.name in [
                'park', 'set_park', 'clean_up', 'goto_sleep', 'get_ready']:
            self.logger.debug("Always safe to move to {}".format(event_data.event.name))
            is_safe = True
        else:
            is_safe = self.is_safe()

        return is_safe

    def mount_is_tracking(self, event_data):
        """ Transitional check for mount.

        This is used as a conditional check when transitioning between certain
        states.
        """
        return self.observatory.mount.is_tracking

    def mount_is_initialized(self, event_data):
        """ Transitional check for mount.

        This is used as a conditional check when transitioning between certain
        states.
        """
        return self.observatory.mount.is_initialized

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
        self.logger.debug(
            "Before calling {} from {} state".format(
                event_data.event.name,
                event_data.state.name))

    def after_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """

        self.logger.debug(
            "After calling {}. Now in {} state".format(
                event_data.event.name,
                event_data.state.name))


##################################################################################################
# Class Methods
##################################################################################################

    @classmethod
    def load_state_table(cls, state_table_name='simple_state_table'):
        """ Loads the state table

        Args:
            state_table_name(str):  Name of state table. Corresponds to file name in
                `$POCS/resources/state_table/` directory or to absolute path if
                starts with "/". Default 'simple_state_table'.

        Returns:
            dict:   Dictionary with `states` and `transitions` keys.
        """

        if not state_table_name.startswith('/'):
            state_table_file = "{}/resources/state_table/{}.yaml".format(
                os.getenv('POCS', default='/var/panoptes/POCS'), state_table_name)
        else:
            state_table_file = state_table_name

        state_table = {'states': [], 'transitions': []}

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except Exception as err:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {} {}'.format(err, state_table_file))

        return state_table

##################################################################################################
# Private Methods
##################################################################################################

    def _lookup_trigger(self):
        self.logger.debug("Source: {}\t Dest: {}".format(self.state, self.next_state))
        if self.state == 'parking' and self.next_state == 'parking':
            return 'set_park'
        else:
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
        s = None
        try:
            state_module = load_module('{}.{}.{}'.format(
                self._states_location.replace("/", "."),
                self._state_table_name,
                state
            ))

            # Get the `on_enter` method
            self.logger.debug("Checking {}".format(state_module))

            on_enter_method = getattr(state_module, 'on_enter')
            setattr(self, 'on_enter_{}'.format(state), on_enter_method)
            self.logger.debug(
                "Added `on_enter` method from {} {}".format(
                    state_module, on_enter_method))

            self.logger.debug("Created state")
            s = State(name=state)

            s.add_callback('enter', '_update_status')

            if can_graph:
                s.add_callback('enter', '_update_graph')

            s.add_callback('enter', 'on_enter_{}'.format(state))

        except Exception as e:
            raise error.InvalidConfig("Can't load state modules: {}\t{}".format(state, e))

        return s

    def _load_transition(self, transition):
        self.logger.debug("Loading transition: {}".format(transition))

        # Add `check_safety` as the first transition for all states
        conditions = listify(transition.get('conditions', []))

        conditions.insert(0, 'check_safety')
        transition['conditions'] = conditions

        self.logger.debug("Returning transition: {}".format(transition))
        return transition
