import Pyro4

from pocs.camera import AbstractCamera


class Camera(AbstractCamera):
    """
    Class representing the interface to a distributed array of cameras
    """
    def __init__(self,
                 name='Pyro Camera Array',
                 model='pyro',
                 *args, **kwargs):
        super().__init__(name=name, model=model, *args, **kwargs)

        self._name_server = self._get_name_server()

    @property
    def name_server(self):
        return self._name_server

    def _get_name_server(self):
        """
        Tries to find Pyro name server.
        """
        name_server = None
        try:
            self.logger.debug("Looking for Pyro name server...")
            name_server = Pyro4.locateNS()
        except Pyro4.errors.NamingError:
            err = "No Pyro name server found!"
            self.logger.error(err)
            raise RuntimeError(err)

        return name_server
