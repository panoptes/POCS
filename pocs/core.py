from .utils.messaging import PanMessaging

from .observatory import Observatory
from .state.logic import PanStateLogic
from .state.machine import PanStateMachine

from . import PanBase


class POCS(PanStateMachine, PanStateLogic, PanBase):

    """ The main class representing the Panoptes Observatory Control Software (POCS).

    Interaction with a PANOPTES unit is done through instances of this class. An instance consists
    primarily of an `Observatory` object, which contains the mount, cameras, scheduler, etc.
    See `pocs.Observatory`. The instance itself is designed to be run as a state machine with
    the `get_ready()` method the transition that is responsible for moving to the initial state.

    Args:
        state_machine_file(str):    Filename of the state machine to use, defaults to 'simple_state_table'
        simulator(list):            A list of the different modules that can run in simulator mode. Possible
            modules include: all, mount, camera, weather, night. Defaults to an empty list.

    """

    def __init__(self, state_machine_file='simple_state_table', messaging=None, **kwargs):

        self.cmd_subscriber = PanMessaging('subscriber', 6501)
        self.msg_publisher = PanMessaging('publisher', 6510)

        # Explicitly call the base classes in the order we want
        PanBase.__init__(self, **kwargs)
        PanStateLogic.__init__(self, **kwargs)
        PanStateMachine.__init__(self, state_machine_file, **kwargs)

        self.logger.info('*' * 80)
        self.logger.info('Initializing PANOPTES unit')

        self.name = self.config.get('name', 'Generic PANOPTES Unit')
        self.logger.info('Welcome {}!'.format(self.name))

        # Create our observatory, which does the bulk of the work
        self.logger.info('\t observatory')
        self.observatory = Observatory(**kwargs)

        self._connected = True
        self._initialized = False

        self.status()

        self.say("Hi there!")

    @property
    def is_initialized(self):
        """ Indicates if POCS has been initalized or not """
        return self._initialized


##################################################################################################
# Methods
##################################################################################################

    def initialize(self):
        """ """

        if not self._initialized:
            self.say("Initializing the system! Woohoo!")

            try:
                # Initialize the mount
                self.logger.debug("Initializing mount")
                self.observatory.mount.initialize()

            except Exception as e:
                self.say("Oh wait. There was a problem initializing: {}".format(e))
                self.say("Since we didn't initialize, I'm going to exit.")
                self.power_down()
            else:
                self._initialized = True

        self.status()
        return self._initialized

    def status(self):
        status = dict()

        try:
            status['state'] = self.state
            status['observatory'] = self.observatory.status()
        except Exception as e:  # pragma: no cover
            self.logger.warning("Can't get status: {}".format(e))

        self.send_message(status, channel='STATUS')

        return status

    def say(self, msg):
        """ PANOPTES Units like to talk!

        Send a message. Message sent out through zmq has unit name as channel.

        Args:
            msg(str): Message to be sent
        """
        self.send_message(msg, channel='PANCHAT')

    def send_message(self, msg, channel='POCS'):
        """ Send a message

        This will use the `self.msg_publisher` to send a message

        Note:
            The `channel` and `msg` params are switched for convenience

        Arguments:
            msg {str} -- Message to be sent

        Keyword Arguments:
            channel {str} -- Channel to send message on (default: {'POCS'})
        """
        self.msg_publisher.send_message(channel, msg)

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
                    if self.observatory.mount.is_parked:
                        self.logger.info("Mount is parked, setting Parked state")
                        self.set_park()

            self.logger.info("Bye!")
            print("Thanks! Bye!")

    def stop_states(self):
        """ Stops the machine loop on the next iteration """
        self.logger.info("Stopping POCS states")
        self._do_states = False
