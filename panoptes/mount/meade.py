import panoptes.utils.serial as serial

class MeadeMount(AbstractMount):
    """ 
    Create a class for Meade mount
    """

    def __init__(self, connect=False, logger=None):
        """ 
        Init Meade mount
        """
        super().__init__() # Call base initialization


    def connect(self):
        """ Connect to the mount via serial """

        # Ping our serial connection
        self.send_command(self.echo())
        ping = self.read_response()
        if ping != 'X#':
            self.logger.error("Connection to mount failed")
        else:
            self.is_connected = True

        return self.is_connected


    def translate_command(self):
        """ Translates command for specific mount """
        raise NotImplementedError()

    def check_coordinates(self):
        """
        Querys the mount for the current position of the mount.
        This will be useful in comparing the position of the mount to the orientation 
        indicated by the accelerometer or by an astrometric plate solve.
        """
        raise NotImplementedError()

    def sync_coordinates(self):
        """
        Takes as input, the actual coordinates (J2000) of the mount and syncs the mount on them.
        Used after a plate solve.
        Once we have a mount model, we would use sync only initially, 
        then subsequent plate solves would be used as input to the model.
        """
        raise NotImplementedError()        

    def slew_to_coordinates(self):
        """
        Inputs:
            HA and Dec
            RA tracking rate (in arcsec per second, use 15.0 in absence of tracking model).
            Dec tracking rate (in arcsec per second, use 0.0 in absence of tracking model).
        """
        raise NotImplementedError()

    def slew_to_park(self):
        """
        No inputs, the park position should be defined in configuration
        """
        raise NotImplementedError()

    def echo(self):
        """ mount-specific echo command """
        raise NotImplementedError()
