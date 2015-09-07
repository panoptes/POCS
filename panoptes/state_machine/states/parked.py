from . import PanState

class State(PanState):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    def execute(self):
        self.logger.info("Inside {} state".format(self.name))
        self._next_state = 'exit'
