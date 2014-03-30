import sys

import panoptes.utils.logger as logger


@logger.do_logging
class Error(Exception):

    """ Base class for Panoptes errors """

    def exit_program(self, msg='No reason specified'):
        """ Kills running program """
        self.logger.error("TERMINATING: {}".format(msg))
        sys.exit()


class InvalidConfig(Error):

    """ Error raised if config file is invalid """

    def __init__(self, msg):
        super(InvalidConfig, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg


class MountNotFound(Error):

    """ Mount cannot be import """

    def __init__(self, m):
        super(MountNotFound, self).__init__()
        self.logger.error('Cannot find mount of type {}'.format(m))
        self.exit_program(msg='No appropriate mount given')

    def __str__(self):
        return self.msg
