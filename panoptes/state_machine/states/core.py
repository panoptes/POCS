import transitions

class PanState(transitions.State):
    """ Base class for PANOPTES transitions """
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', self.__class__)
        super().__init__(name=name, on_enter=['weather_is_safe','execute'], on_exit=['weather_is_safe'])

    def main(self):
        pass
