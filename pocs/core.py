import os

from .utils import error
from .utils.database import PanMongo
from .utils.messaging import PanMessaging

from .observatory import Observatory
from .state.logic import PanStateLogic
from .state.machine import PanStateMachine

from . import _config
from . import _logger


class POCS(PanStateMachine, PanStateLogic):

    """ The main class representing the Panoptes Observatory Control Software (POCS).

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `pocs.Observatory`. The instance itself is designed to be run as a state machine with
    the `get_ready()` method the transition that is responsible for moving to the initial state.

    Args:
        state_machine_file(str):    Filename of the state machine to use, defaults to 'simple_state_table'
        simulator(list):            A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather. Defaults to an empty list.

    """

    def __init__(self, state_machine_file='simple_state_table', simulator=[], **kwargs):
        self.config = _config
        self.logger = _logger

        self.messaging = kwargs.get('messaging', PanMessaging(publisher=True, connect=True, bind=False))

        # Explicitly call the base classes in the order we want
        PanStateLogic.__init__(self, **kwargs)
        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES unit')

        self.name = self.config.get('name', 'Generic PANOPTES Unit')
        self.logger.info('Welcome {}!'.format(self.name))

        # Database
        if not self.db:
            self.logger.info('\t database connection')
            self.db = PanMongo()

        # Remove logger information from config saved to mongo
        del self.config['logger']
        self.db.insert_current('config', self.config)

        # Simulator
        if 'all' in simulator:
            simulator = ['camera', 'mount', 'weather']
        self.config.setdefault('simulator', simulator)

        # Create our observatory, which does the bulk of the work
        self.logger.info('\t observatory')
        self.observatory = Observatory(config=self.config, **kwargs)

        self._connected = True
        self._initialized = False

        self.say("Hi there!")


##################################################################################################
# Methods
##################################################################################################

    def status(self):
        status = dict()

        try:
            status['state'] = self.state
            status['observatory'] = self.observatory.status()

            self.messaging.send_message('STATUS', status)
        except:
            self.logger.warning("Can't get status")

        return status

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message. Message sent out through zmq has unit name as channel.

        Args:
            msg(str): Message to be sent
        """
        self.logger.info("{} says: {}".format(self.name, msg))
        self.messaging.send_message('SAYBOT', msg)

    def initialize(self):
        """ """

        if not self._initialized:
            self.say("Initializing the system! Woohoo!")

            try:
                # Initialize the mount
                self.logger.debug("Initializing mount")
                self.observatory.mount.initialize()

                # Initialize each of the cameras while slewing
                for cam in self.observatory.cameras.values():
                    self.logger.debug("Initializing camera: {}".format(cam))
                    cam.connect()

                else:
                    raise error.InvalidMountCommand("Mount not initialized")

            except Exception as e:
                self.say("Oh wait. There was a problem initializing: {}".format(e))
                self.say("Since we didn't initialize, I'm going to exit.")
                self.power_down()
            else:
                self._initialized = True

        return self._initialized

    def power_down(self):
        """ Actions to be performed upon shutdown

        Note:
            This method is automatically called from the interrupt handler. The definition should
            include what you want to happen upon shutdown but you don't need to worry about calling
            it manually.
        """
        if self._connected:
            self.logger.info("Shutting down {}, please be patient and allow for exit.".format(self.name))

            # Observatory shut down
            self.observatory.power_down()

            # Park if needed
            if self.state not in ['parking', 'parked', 'sleeping', 'housekeeping']:
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.park()

            if self.state == 'parking':
                if self.observatory.mount.is_connected:
                    if not self.observatory.mount.is_parked:
                        self.logger.info("Parking mount")
                        self.set_park()

            self.logger.info("Bye!")
            print("Thanks! Bye!")

            # Remove shutdown file
            if os.path.exists(self._shutdown_file):
                os.unlink(self._shutdown_file)

            self._connected = False
