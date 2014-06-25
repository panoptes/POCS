"""
.. module:: state
    :synoposis: Represents a valid `State`

"""

import panoptes.utils.logger as logger
import panoptes.utils.error as error

@logger.has_logger
class StateMachine(object):
    """
    The Panoptes StateMachine
    """
    def __init__(self, observatory):
        self.handlers = {}
        self.start_state = None
        self.end_states = []

        self.observatory = observatory

    def add_state(self, name, handler, end_state=0):
        name = name.upper()
        self.handlers[name] = handler
        if end_state:
            self.end_states.append(name)

    def set_start(self, name):
        self.start_state = name.upper()

    def start_session(self):
        """
        Begins moving through a nightly session. Loads the `start_state`
        handler. Handler is passed the current `observatory` and is expected
        to return a `new_state`, which is used to lookup the next handler
        """
        try:
            handler = self.handlers[self.start_state]
        except:
            self.logger.error("must call .set_start() before .run()")
            raise "InitializationError"

        if not self.end_states:
            raise  "InitializationError"
            self.logger.error("at least one state must be an end_state")

        # Stop looping until we receive an end_state
        while True:

            # Actually call the handler and get new_state
            new_state = handler(self.observatory)
            
            if new_state.upper() in self.end_states:
                break
            else:
                handler = self.handlers[new_state.upper()]    