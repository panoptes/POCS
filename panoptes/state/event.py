import sys


class PanEventManager(object):

    """ The event loop logic for the unit """

    def __init__(self, loop_delay=5, **kwargs):

        # Get the asyncio loop
        self.logger.debug("Setting up the event loop")

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
                self.get_ready()
            else:
                self.logger.warning("Not safe, calling wait_until_safe")
                self.wait_until_safe()

        except KeyboardInterrupt:
            self.logger.warning("Interrupted")
            self.power_down()
        finally:
            self.logger.debug("Done running")

    def power_down(self):
        raise NotImplementedError()

##################################################################################################
# Private Methods
##################################################################################################

