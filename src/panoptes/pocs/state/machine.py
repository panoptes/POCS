import os

from contextlib import suppress
from transitions.extensions.states import Tags as MachineState

from panoptes.utils import error
from panoptes.utils import listify
from panoptes.utils.library import load_module
from panoptes.utils.serializers import from_yaml

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

        # Setup Transitions.
        _transitions = [self._load_transition(transition)
                        for transition in state_machine_table['transitions']]

        # States can require the horizon to be at a certain level.
        self._horizon_lookup = dict()

        # Setup States.
        states = [
            self._load_state(state, state_info=state_info)
            for state, state_info
            in state_machine_table.get('states', dict()).items()
        ]

        self.logger.debug(f'Horizon limits: {self._horizon_lookup!r}')

        # Create state machine.
        super(PanStateMachine, self).__init__(
            states=states,
            transitions=_transitions,
            initial=state_machine_table.get('initial'),
            send_event=True,
            before_state_change='before_state',
            after_state_change='after_state',
            auto_transitions=False,
            name="POCS State Machine",
            **kwargs
        )

        self._state_machine_table = state_machine_table
        self.next_state = None
        self.run_once = kwargs.get('run_once', False)

        self.logger.debug("State machine created")

    ##################################################################################################
    # Properties
    ##################################################################################################

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
                has become False, otherwise will wait (default)
            run_once (bool, optional): If the machine loop should only run one time, defaults
                to False to loop continuously.
        """
        assert self.is_initialized, self.logger.error("POCS not initialized")

        run_once = run_once or self.run_once

        # Start with `get_ready`
        self.next_state = 'ready'

        _loop_iteration = 0
        self.logger.debug(f'Starting run loop with keep_running={self.keep_running} '
                          f'and connected={self.connected}')
        while self.keep_running and self.connected:
            state_changed = False
            self.logger.info(f'Run loop: state={self.state} next_state={self.next_state} do_states={self.do_states}')

            # If we are processing the states
            self.logger.debug(f'Observatory can_observe: {self.observatory.can_observe}')
            if self.do_states and self.observatory.can_observe:

                # BEFORE TRANSITION

                # Wait for safety readying at given horizon level.
                required_horizon = self._horizon_lookup.get(self.next_state, 'observe')
                delay = self.get_config('wait_delay', default=60 * 3)  # Check every 3 minutes
                self.logger.debug(f'Checking for horizon={required_horizon} for {self.next_state}')
                while not self.is_safe(no_warning=True, horizon=required_horizon):
                    self.logger.info(f'Waiting for horizon={required_horizon} for state={self.next_state}')
                    self.wait(delay=delay)

                # ENTER STATE

                self.logger.info(f'Going to next_state={self.next_state}')
                try:
                    # The state's `on_enter` logic will be performed here.
                    state_changed = self.goto_next_state()
                except Exception as e:
                    self.logger.critical(f"Problem going from {self.state} to {self.next_state}, exiting loop [{e!r}]")
                    # TODO should we automatically park here?
                    self.stop_states()
                    break

                # AFTER TRANSITION

                # If we didn't successfully transition, wait a while then try again
                max_iterations = self.get_config('pocs.MAX_TRANSITION_ATTEMPTS', default=5)
                if not state_changed:
                    self.logger.warning(f"Failed to move from {self.state} to {self.next_state}")
                    if self.is_safe() is False:
                        self.logger.warning("Conditions have become unsafe; setting next state to 'parking'")
                        self.next_state = 'parking'
                    elif _loop_iteration > max_iterations:
                        self.logger.warning(f"Stuck in current state for {max_iterations} iterations, parking")
                        self.next_state = 'parking'
                    else:
                        _loop_iteration = _loop_iteration + 1
                        self.logger.warning(f"Sleeping before trying again ({_loop_iteration}/{max_iterations})")
                        self.wait(with_status=False)
                else:
                    _loop_iteration = 0

                # Note that `self.state` below has changed from above
                # If we are in ready state then we are making one attempt through the loop.
                if self.state == 'ready':
                    self._obs_run_retries -= 1

                if self.state == 'sleeping' and run_once:
                    self.stop_states()
            elif exit_when_done:
                break
            elif not self.interrupted:
                # Sleep for one minute
                self.logger.debug(f'Sleeping in run loop - why am I here?')
                self.wait(delay=60)

    def goto_next_state(self):
        """Make a transition to the next state.

        Each state is responsible for setting the `next_state` property based
        off the logic that happens inside the state. This method will look up
        the transition method to reach the next state and call that method.

        If no transition method is defined for whatever is set as `next_state`
        then the `park` method will be called.

        Returns:
            bool: If state was successfully changed.
        """
        state_changed = False

        # Get the next transition method based off `state` and `next_state`
        transition_method_name = self._lookup_trigger()
        transition_method = getattr(self, transition_method_name, self.park)
        self.logger.debug(f'{transition_method_name}: {self.state} → {self.next_state}')

        # Do transition.
        state_changed = transition_method()
        if state_changed:
            self.logger.success(f'Successful transition to {self.state}')
            self.db.insert_current('state', {"source": self.state, "dest": self.next_state})

        return state_changed

    def stop_states(self):
        """ Stops the machine loop on the next iteration """
        self.logger.success("Stopping POCS states")
        self.do_states = False

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

        self.logger.debug(f"Checking safety for {event_data.transition}")

        if event_data is None:
            return self.is_safe()

        dest_state_name = event_data.transition.dest
        dest_state = self.get_state(dest_state_name)

        # See if the state requires a certain horizon limit.
        required_horizon = self._horizon_lookup.get(dest_state_name, 'observe')

        # It's always safe to be in some states
        if dest_state.is_always_safe:
            self.logger.debug(f"Always safe to move to {dest_state_name}")
            is_safe = True
        else:
            is_safe = self.is_safe(horizon=required_horizon)

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

        Args:
            event_data(transitions.EventData):  Contains information about the event
         """
        self.logger.debug(f"Changing state from {event_data.state.name} to {event_data.event.name}")

    def after_state(self, event_data):
        """ Called after each state.

        Args:
            event_data(transitions.EventData):  Contains information about the event
        """

        self.logger.debug(f"After {event_data.event.name} transition. In {event_data.state.name} state")

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
            state_table_file = os.path.join(
                os.getenv('POCS', default='/var/panoptes/POCS'),
                'resources',
                'state_table',
                f'{state_table_name}.yaml'
            )
        else:
            state_table_file = state_table_name

        try:
            with open(state_table_file, 'r') as f:
                state_table = from_yaml(f.read())
        except Exception as err:
            raise error.InvalidConfig(f'Problem loading state table yaml file: {err!r} {state_table_file}')

        return state_table

    ##################################################################################################
    # Private Methods
    ##################################################################################################

    def _lookup_trigger(self):
        if self.state == 'parking' and self.next_state == 'parking':
            return 'set_park'
        else:
            for state_info in self._state_machine_table['transitions']:
                if self.state in state_info['source'] and state_info['dest'] == self.next_state:
                    return state_info['trigger']

        # Return parking if we don't find anything
        return 'parking'

    def _update_status(self, event_data):
        self.logger.debug(f'State change status: {self.status!r}')

    def _load_state(self, state, state_info=None):
        self.logger.debug(f"Loading state: {state}")
        state_machine = None
        try:
            state_module = load_module('panoptes.{}.{}.{}'.format(
                self._states_location.replace("/", "."),
                self._state_table_name,
                state
            ))

            # Get the `on_enter` method
            self.logger.debug(f"Checking {state_module}")

            on_enter_method = getattr(state_module, 'on_enter')
            setattr(self, f'on_enter_{state}', on_enter_method)
            self.logger.debug(f"Added `on_enter` method from {state_module} {on_enter_method}")

            if state_info is None:
                state_info = dict()

            # Add horizon if state requires.
            with suppress(KeyError):
                self._horizon_lookup[state] = state_info['horizon']
                del state_info['horizon']

            self.logger.debug(f"Creating state={state} with {state_info}")
            state_machine = MachineState(name=state, **state_info)

            # Add default callbacks.
            state_machine.add_callback('enter', '_update_status')
            state_machine.add_callback('enter', f'on_enter_{state}')

        except Exception as e:
            raise error.InvalidConfig(f"Can't load state modules: {state}\t{e!r}")

        return state_machine

    def _load_transition(self, transition):
        self.logger.debug(f"Loading transition: {transition}")

        # Add `check_safety` as the first transition for all states
        conditions = listify(transition.get('conditions', []))

        conditions.insert(0, 'check_safety')
        transition['conditions'] = conditions

        self.logger.debug(f"Returning transition: {transition}")
        return transition
