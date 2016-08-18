import os

from json import loads

import yaml
import zmq

from transitions import Machine
from transitions import State

from ..utils import error
from ..utils import listify
from ..utils import load_module


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
    def next_state(self):
        return self._next_state

    @next_state.setter
    def next_state(self, value):
        """ Set the tracking rate """
        self._next_state = value

##################################################################################################
# Methods
##################################################################################################

    def run(self):
        """ Runs the state machine loop

        This runs the state machine in a loop. Setting the machine proprety
        `is_running` to False will stop the loop.
        """
        assert self.is_initialized, self.logger.error("POCS not initialized")

        self._keep_running = True

        # Start with `get_ready`
        self.next_state = 'ready'

        _loop_iteration = 0

        check_messages = self._get_message_checker()

        while self.keep_running:
            state_changed = False

            check_messages()

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
                except KeyboardInterrupt:
                    self.logger.warning("Interrupted, stopping")
                    self.stop_machine()
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

            else:
                self.sleep(1)


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
        # self.db.insert_current('state', {'state': event_data.state.name, 'event': event_data.event.name})
        self.logger.debug("Before calling {} from {} state".format(event_data.event.name, event_data.state.name))

    def after_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """

        # self.db.insert_current('state', {'state': event_data.state.name, 'event': event_data.event.name})
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
            if state_info['source'] == self.state and state_info['dest'] == self.next_state:
                return state_info['trigger']

        # Return parking if we don't find anything
        return 'parking'

    def _update_status(self, event_data):
        self.status()

    def _update_graph(self, event_data):
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

                # s.add_callback('enter', '_update_graph')

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

    def _get_message_checker(self):
        """Create a function that checks for incoming ZMQ messages

        Typically this will be the POCS_shell but could also be PAWS in the future.
        These messages arrive via 0MQ and are processed during each iteration of
        the event loop.

        Returns:
            code: A callable function that handles ZMQ messages
        """
        poller = zmq.Poller()
        poller.register(self.cmd_subscriber.subscriber, zmq.POLLIN)

        def check_message():

            # Poll for messages
            sockets = dict(poller.poll(500))  # 500 ms timeout

            if self.cmd_subscriber.subscriber in sockets and sockets[self.cmd_subscriber.subscriber] == zmq.POLLIN:

                msg_type, msg = self.cmd_subscriber.subscriber.recv_string(flags=zmq.NOBLOCK).split(' ', maxsplit=1)
                msg_obj = loads(msg)
                self.logger.info("Incoming message: {} {}".format(msg_type, msg_obj))

                cmd = msg_obj['message']

                if cmd == 'run':
                    self.logger.info("Starting loop from pocs_shell")
                    self.next_state = 'ready'
                    self._do_states = True

                if cmd == 'park':
                    if self.state not in ['parked', 'parking', 'sleeping', 'housekeeping']:
                        self.next_state = 'parking'

        return check_message
