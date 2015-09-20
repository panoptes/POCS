import subprocess
import os
import re
import numpy as np

from . import has_logger
from . import InvalidSystemCommand
from . import listify

@has_logger
class Image(object):
    """ Class for working with images

    Note:
        Many functions need dcraw to be installed.
    """
    def __init__(self, filenames):
        super().__init__()

        # Save the list of files
        self.files = [f if os.path.exists(f) for f in listify(fname)]
        self.logger.debug("{} files loaded.".format(len(self.files)))

    def to_pgm(self):
        """ Converts CR2 to PGM using dcraw """

        for f in self.files:
            self.logger.debug("Converting {} to pgm".format(f))
            try:
                # Build the command for this file
                command = 'dcraw -t 0 -D -4 {}'.format(self.fname)
                cmd_list = command.split()
                self.logger.debug("CR2 to PGM Conversion command: \n {}".format(cmd_list))

                # Run the command
                if subprocess.check_call(cmd_list) == 0:
                    self.logger.debug("PGM Conversion command successful")

            except subprocess.CalledProcessError as err:
                raise InvalidSystemCommand(msg="File: {} \n err: {}".format(f, err))


    def read_pgm(fname, byteorder='>'):
        """Return image data from a raw PGM file as numpy array.

        Format specification: http://netpbm.sourceforge.net/doc/pgm.html

        """
        with open(filename, 'rb') as f:
            buffer = f.read()
        try:
            header, width, height, maxval = re.search(
                b"(^P5\s(?:\s*#.*[\r\n])*"
                b"(\d+)\s(?:\s*#.*[\r\n])*"
                b"(\d+)\s(?:\s*#.*[\r\n])*"
                b"(\d+)\s(?:\s*#.*[\r\n]\s)*)", buffer).groups()
        except AttributeError:
            raise ValueError("Not a raw PGM file: '%s'" % filename)
        return np.frombuffer(buffer,
                             dtype='u1' if int(maxval) < 256 else byteorder + 'u2',
                             count=int(width) * int(height),
                             offset=len(header)
                             ).reshape((int(height), int(width)))
