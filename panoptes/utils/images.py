import subprocess
import os
import re
import numpy as np

from . import InvalidSystemCommand
from . import listify

def cr2_to_pgm(cr2, pgm=None, dcraw='/usr/bin/dcraw', clobber=True, logger=None):
    """ Converts CR2 to PGM using dcraw

    Args:
        cr2(str):           Filename of CR2 to be converted
        pgm(str, optional): Name of PGM output file. Optional. If nothing is provided
            then the PGM will have the same name as the input file but with the .pgm extension
        dcraw(str):         dcraw binary
        clobber(bool):      Clobber existing PGM or not. Defaults to True

    Returns:
        str:   PGM file name
    """
    assert os.path.exists(dcraw), "dcraw does not exist at location {}".format(dcraw)
    assert os.path.exists(cr2), "cr2 file does not exist at location {}".format(cr2)

    if logger is None:
        logger = PrintLog()

    if pgm is None:
        pgm_fname = cr2.replace('.cr2', '.pgm')
    else:
        pgm_fname = pgm

    if os.path.exists(pgm_fname) and not clobber:
        logger.debug("PGM file exists and clobber=False, returning existing file: {}".format(pgm_fname))
    else:
        try:
            # Build the command for this file
            command = '{} -t 0 -D -4 {}'.format(dcraw, cr2)
            cmd_list = command.split()
            logger.debug("PGM Conversion command: \n {}".format(cmd_list))

            # Run the command
            if subprocess.check_call(cmd_list) == 0:
                logger.debug("PGM Conversion command successful")

        except subprocess.CalledProcessError as err:
            raise InvalidSystemCommand(msg="File: {} \n err: {}".format(cr2, err))

    return pgm_fname

def read_pgm(pgm, byteorder='>', logger=None):
    """Return image data from a raw PGM file as numpy array.

    Format specification: http://netpbm.sourceforge.net/doc/pgm.html

    http://stackoverflow.com/questions/7368739/numpy-and-16-bit-pgm
    """
    if logger is None:
        logger = PrintLog()

    with open(pgm, 'rb') as f:
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


class PrintLog(object):
    """ Prints messages. Used when no logger exists """
    def __init__(self):
        printer = lambda x: print(x)

        for a in ['debug']:
            setattr(self, a, printer)
