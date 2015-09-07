from . import PanState

class State(PanState):
    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    def main(self):
        return 'exit'
