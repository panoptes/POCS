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

        # Get a proxy for the name server (will raise NamingError if not found)
        self._name_server = Pyro4.locateNS()

    @property
    def name_server(self):
        return self._name_server

    def _get_name_server(self):
        """
        Tries to find Pyro name server and returns a proxy to it.
        """
        name_server = None
        try:
            name_server = Pyro4.locateNS()
        except Pyro4.errors.NamingError:
            err = "No Pyro name server found!"
            self.logger.error(err)
            raise RuntimeError(err)

        return name_server

    def _get_camera_list(self):
        """
        Queries the name server for a list of all registered POCS
        Camera objects.
        """
        return self.name_server.list(metadata_all={'POCS', 'Camera'})
