from . import PanState


class State(PanState):
    def __init__(self, *arg, **kwargs):
        super().__init__(self, *arg, **kwargs)
        self.logger.info("In shutdown")
