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

    Args:
        filenames(str or list):     A str or list of strings of filenames
        dcraw(str):                 Location of dcraw executable. Defaults to `/usr/bin/dcraw`
        clobber(bool):              Whether or not files should be clobbered. Defaults to True.
    """

    def __init__(self, filenames, dcraw='/usr/bin/dcraw', clobber=True):
        super().__init__()

        self.clobber = clobber

        assert os.path.exists(dcraw), self.logger.warning("dcraw does not exist at location {}".format(dcraw))
        self.dcraw = dcraw

        # Save the list of files
        self.files = [f if os.path.exists(f) else None for f in listify(filenames)]
        self.logger.debug("{} files loaded.".format(len(self.files)))

    def cr2_to_pgm(self):
        """ Converts CR2 to PGM using dcraw

        Returns:
            list:   PGM file names
        """
        pgm_files = []

        for f in self.files:
            if f is None:
                continue

            pgm_fname = f.replace('.cr2', '.pgm')

            if os.path.exists(pgm_fname) and not self.clobber:
                self.logger.warning("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
                pgm_files.append(pgm_fname)
                continue

            self.logger.debug("Converting {} to pgm".format(f))
            try:

                # Build the command for this file
                command = '{} -t 0 -D -4 {}'.format(self.dcraw, f)
                cmd_list = command.split()
                self.logger.debug("CR2 to PGM Conversion command: \n {}".format(cmd_list))

                # Run the command
                if subprocess.check_call(cmd_list) == 0:
                    self.logger.debug("PGM Conversion command successful")
                    pgm_files.append(pgm_fname)

            except subprocess.CalledProcessError as err:
                raise InvalidSystemCommand(msg="File: {} \n err: {}".format(f, err))

        return pgm_files

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
