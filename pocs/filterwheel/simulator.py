from pocs.filterwheel import AbstractFilterWheel


class FilterWheel(AbstractFilterWheel):
    """
    Class for simulated filter wheels.

    Args:
        name (str, optional): name of the filter wheel
        model (str, optional): model of the filter wheel
        camera (pocs.camera.*.Camera, optional): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
    """
    def __init__(self,
                 name='Simulated filter wheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 *args, **kwargs):

        super().__init__(name=name,
                         model=model,
                         camera=camera,
                         filter_names=filter_names,
                         *args, **kwargs)

    @property
    def position(self):
        """ """
        pass

    def move_to(self, position):
        pass
