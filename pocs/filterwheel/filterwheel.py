from pocs.base import PanBase

class AbstractFilterWheel(PanBase):
    """
    Base class for all filter wheels

    Args:
        name (str, optional): name of the focuser
        model (str, optional): model of the focuser
        camera (pocs.camera.Camera, optional): camera that this filter wheel is associated with.
        filter_names (list of str): names of the filters installed at each filter wheel position
    """
    def __init__(self,
                 name='Generic Filterwheel',
                 model='simulator',
                 camera=None,
                 filter_names=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = model
        self.name = name

        self._connected = False
        self._serial_number = 'XXXXXX'

##################################################################################################
# Methods
##################################################################################################

def go_to(self, position):
    """

    """
    raise NotImplementedError


def _fits_header(self, header):
    header.set('FW-NAME', self.name, 'Filter wheel name')
    header.set('FW-MOD', self.model, 'Filter wheel model')
    header.set('FW-ID', self.uid, 'Filter wheel serial number')
    header.set('FW-POS', self.position, 'Filter wheel position')
    header.set('FILTER', self.filter_names[self.position], 'Filter name')
    return header


def __str__(self):
    return "{} ({}) on {}".format(self.name, self.uid, self.port)
