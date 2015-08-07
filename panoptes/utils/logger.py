from astropy import log

def has_logger(Class, level='DEBUG'):
    """Class decorator to add logging

    Args:
        level (str): log level to set for the class wrapper, defaults to 'warning'
    """
    log.setLevel(level)
    log.info("Adding {} logging to: {}".format(level, Class.__name__))
    setattr(Class, 'logger', log)
    return Class
