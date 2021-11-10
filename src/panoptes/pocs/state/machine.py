import os
from contextlib import suppress

from transitions.extensions.states import Tags as MachineState
from transitions import Machine
from panoptes.utils import error
from panoptes.utils.utils import listify
from panoptes.utils.library import load_module
from panoptes.utils.serializers import from_yaml


class PanStateMachine(Machine):
    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit.
    """

    def __init__(self, state_machine_table, **kwargs):

        if isinstance(state_machine_table, str):
            self.logger.info(f"Loading state table: {state_machine_table}")
            state_machine_table = PanStateMachine.load_state_table(
                state_table_name=state_machine_table)

        assert 'states' in state_machine_table, self.logger.warning('states keyword required.')
        assert 'transitions' in state_machine_table, self.logger.warning(
            'transitions keyword required.')

        self._state_table_name = state_machine_table.get('name', 'default')
        self._states_location = state_machine_table.get('location', 'panoptes.pocs.state.states')

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

        self.logger.debug("State machine created")

    ################################################################################################
    # Properties
    ################################################################################################

    @property
    def next_state(self):
        return self._next_state

    @next_state.setter
    def next_state(self, value):
        """ Set the tracking rate """
        self._next_state = value

    ################################################################################################
    # Methods
    ################################################################################################

    def run(self, exit_when_done=False, run_once=False, initial_next_state='ready'):
        """Runs the state machine loop.

        This runs the state machine in a loop. Setting the machine property
        `is_running` to False will stop the loop.

        Args:
            exit_when_done (bool, optional): If True, the loop will exit when `do_states`
                has become False, otherwise will wait (default)
            run_once (bool, optional): If the machine loop should only run one time, defaults
                to False to loop continuously.
            initial_next_state (str, optional): The first state the machine should move to from
                the `sleeping` state, default `ready`.
        """
        if not self.is_initialized:
            self.logger.warning("POCS not initialized")
            return False

        run_once = run_once or self.run_once

        self.next_state = initial_next_state

        _transition_iteration = 0
        max_transition_attempts = self.get_config('max_transition_attempts', default=5)
        check_delay = self.get_config('wait_delay', default=120)

        self.logger.debug(f'Starting run loop')
        while self.keep_running:

            # BEFORE TRANSITION TO STATE
            self.logger.info(f'Run loop: {self.state!r} -> {self.next_state!r}')

            # Before moving to next state, wait for required horizon if necessary.
            while True:
                # If not safe, go to park
                is_safe = self.is_safe(park_if_not_safe=True, ignore=['is_dark'])

                # The state may have changed since the start of the while loop
                # e.g. if self.park is called from self.is_safe
                # So we need to check if the new state is always safe
                if self.get_state(self.next_state).is_always_safe:
                    break

                # Check the horizon here because next state may have changed in loop.
                required_horizon = self._horizon_lookup.get(self.next_state, 'observe')
                if self.is_dark(horizon=required_horizon):
                    break

                # Sleep before checking again.
                self.logger.info(f"Waiting for {required_horizon=!r} for {self.next_state=!r}")
                self.wait(delay=check_delay)

            # TRANSITION TO STATE
            self.logger.info(f'Going to {self.next_state!r}')
            try:
                # The state's `on_enter` logic will be performed here.
                state_changed = self.goto_next_state()
            except Exception as e:
                self.logger.critical(f"Problem going from {self.state!r} to {self.next_state!r}, "
                                     f"exiting loop [{e!r}]")
                # TODO should we automatically park here?
                self.stop_states()
                break

            # AFTER TRANSITION TO STATE (NOW INSIDE STATE)

            # If we didn't successfully transition, wait a while then try again
            if not state_changed:
                self.logger.warning(f"Failed to move from {self.state!r} to {self.next_state!r}")
                if self.is_safe() is False:
                    self.logger.warning(
                        "Conditions have become unsafe; setting next state to 'parking'")
                    self.next_state = 'parking'
                elif _transition_iteration > max_transition_attempts:
                    self.logger.warning(
                        f"Stuck in current state for {max_transition_attempts=!r}, parking")
                    self.next_state = 'parking'
                else:
                    _transition_iteration = _transition_iteration + 1
                    self.logger.warning(
                        f"Sleeping before trying again ({_transition_iteration}/"
                        f"{max_transition_attempts})")
                    self.wait(delay=7)  # wait 7 seconds (no good reason)
            else:
                _transition_iteration = 0

            # Note that `self.state` below has changed from above

            # We started in the sleeping state, so if we are back here we have done a full loop.
            if self.state == 'sleeping':
                self.logger.debug('State machine loop complete, decrementing retry attempts')
                self._obs_run_retries -= 1
                if run_once:
                    self.stop_states()

                if exit_when_done:
                    self.logger.info(f'Leaving run loop {exit_when_done=!r}')
                    break

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
        # Get the next transition method based off `state` and `next_state`
        transition_method_name = self._lookup_trigger()
        transition_method = getattr(self, transition_method_name, self.park)
        self.logger.debug(f'{transition_method_name}: {self.state} → {self.next_state}')

        # Do transition logic.
        state_changed = transition_method()
        if state_changed:
            self.logger.success(f'Finished with {self.state}')
            self.db.insert_current('state', {"source": self.state, "dest": self.next_state})

        return state_changed

    def stop_states(self):
        """ Stops the machine loop on the next iteration by setting do_states=False """
        self.logger.success("Stopping POCS states")
        self.do_states = False

    ################################################################################################
    # State Conditions
    ################################################################################################

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

    ################################################################################################
    # Callback Methods
    ################################################################################################

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

        self.logger.debug(
            f"After {event_data.event.name} transition. In {event_data.state.name} state")

    ################################################################################################
    # Class Methods
    ################################################################################################

    @classmethod
    def load_state_table(cls, state_table_name='panoptes'):
        """ Loads the state table
        Args:
            state_table_name(str):  Name of state table. Corresponds to filename in
                `$POCS/conf_files/state_table/` directory or to absolute path if
                starts with "/". Default 'panoptes.yaml'.
        Returns:
            dict:   Dictionary with `states` and `transitions` keys.
        """

        if not state_table_name.startswith('/'):
            state_table_file = os.path.join(
                os.getenv('POCS', default='/panoptes-pocs'),
                'conf_files',
                'state_table',
                f'{state_table_name}.yaml'
            )
        else:
            state_table_file = state_table_name

        try:
            with open(state_table_file, 'r') as f:
                state_table = from_yaml(f.read())
        except Exception as err:
            raise error.InvalidConfig(
                f'Problem loading state table yaml file: {err!r} {state_table_file}')

        return state_table

    ################################################################################################
    # Private Methods
    ################################################################################################

    def _lookup_trigger(self):
        if self.state == 'parking' and self.next_state == 'parking':
            return 'set_park'
        else:
            for state_info in self._state_machine_table['transitions']:
                if self.state in state_info['source'] and state_info['dest'] == self.next_state:
                    return state_info['trigger']

        # Return parking if we don't find anything
        self.logger.warning(f'No transition for {self.state} -> {self.next_state}, going to park')
        return 'parking'

    def _update_status(self, event_data):
        self.logger.debug(f'State change status: {self.status!r}')

    def _load_state(self, state, state_info=None):
        self.logger.debug(f"Loading state: {state}")
        try:
            state_location = self._states_location.replace("/", ".")
            state_module = load_module(f"{state_location}.{self._state_table_name}.{state}")

            # Get the `on_enter` method
            self.logger.debug(f"Checking {state_module}")

            on_enter_method = getattr(state_module, 'on_enter')
            setattr(self, f'on_enter_{state}', on_enter_method)
            self.logger.trace(f"Added `on_enter` method from {state_module} {on_enter_method}")

            if state_info is None:
                state_info = dict()

            # Add horizon if state requires.
            with suppress(KeyError):
                self._horizon_lookup[state] = state_info['horizon']
                del state_info['horizon']

            self.logger.debug(f"Creating state={state!r} with state_info={state_info!r}")
            state_machine = MachineState(name=state, **state_info)

            # Add default callbacks.
            state_machine.add_callback('enter', '_update_status')
            state_machine.add_callback('enter', f'on_enter_{state}')

        except Exception as e:
            raise error.InvalidConfig(f"Can't load state modules: {state}\t{e!r}")

        return state_machine

    def _load_transition(self, transition):
        # Add `check_safety` as the first transition for all states
        conditions = listify(transition.get('conditions', []))

        conditions.insert(0, 'check_safety')
        transition['conditions'] = conditions

        self.logger.trace(f"Returning transition: {transition}")
        return transition
