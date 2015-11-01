from ..utils.indi import PanIndiDevice


class AbstractCamera(PanIndiDevice):

    """ Abstract Camera class

    Args:
        name(str):      Name for the camera, defaults to 'GenericCamera'
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """
    pass

    def __init__(self, config):
        super().__init__(config)

        self.properties = None
        self.cooled = True
        self.cooling = False

        self.logger.info('Camera {} created on {}'.format(self.name, self.config.get('port')))

##################################################################################################
# Methods
##################################################################################################

    def construct_filename(self):
        """
        Use the filename_pattern from the camera config file to construct the
        filename for an image from this camera
        """
        # Create an object for just the camera config items
        self.filename_pattern = self.camera_config.get('filename_pattern')
