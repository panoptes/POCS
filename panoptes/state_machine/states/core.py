import transitions

class PanState(transitions.State):
    """ Base class for PANOPTES transitions """
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', self.__class__)
        super().__init__(name=name)

        # Add the weather_is_safe callback to all states
        self.add_callback('enter', 'execute')
        self.add_callback('enter', 'weather_is_safe')
        self.add_callback('exit', 'weather_is_safe')
