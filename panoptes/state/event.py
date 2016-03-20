import sys
import asyncio
import signal
from functools import partial


class PanEventManager(object):

    """ The event loop logic for the unit """

    def __init__(self, loop_delay=5, **kwargs):

        # Get the asyncio loop
        self.logger.debug("Setting up the event loop")
        self._loop = asyncio.get_event_loop()

        if kwargs.get('debug', False):
            self._loop.set_debug(True)

        # When we want to loop things
        self._loop_delay = loop_delay

        # Setup utils for graceful shutdown
        self.logger.debug("Setting up interrupt handlers for state machine")
        self._loop.add_signal_handler(signal.SIGTERM, partial(self._sigint_handler))

##################################################################################################
# Methods
##################################################################################################
    def run(self):
        """ Runs the event loop

        This method starts the main asyncio event loop and stays in the loop until a SIGINT or
        SIGTERM is received (see `_sigint_handler`)
        """
        try:
            self.logger.debug("Starting event loop and calling `get_ready`")

            if self.is_safe():
                self.logger.debug("System safe, calling get_ready")
                self._loop.call_soon(self.get_ready)
            else:
                self.logger.warning("Not safe, calling wait_until_safe")
                self._loop.call_soon(self.wait_until_safe)

            self._loop.run_forever()
        except KeyboardInterrupt:
            self.logger.warning("Interrupted")
            self.power_down()
        finally:
            self.logger.debug("Event loop stopped")
            if self._loop.is_running():
                self.logger.debug("Stopping event loop")
                self._loop.stop()

            if not self._loop.is_closed():
                self.logger.debug("Closing event loop")
                self._loop.close()

    def power_down(self):
        raise NotImplementedError()

##################################################################################################
# Private Methods
##################################################################################################

    def _sigint_handler(self):
        """
        Interrupt signal handler. Designed to intercept a Ctrl-C from
        the user and properly shut down the system.
        """
        self.logger.error("System interrupt, shutting down")
        try:
            self.logger.debug("Powering down")
            self.power_down()
        except Exception as e:
            self.logger.error("Problem powering down. PLEASE MANUALLY INSPECT THE MOUNT.")
            self.logger.error("Error: {}".format(e))
        finally:
            sys.exit(0)
