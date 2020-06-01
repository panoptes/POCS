# This module enables a test to provide a handler for "hooked://..." urls
# passed into serial.serial_for_url. To do so, set the value of
# serial_class_for_url from your test to a function with the same API as
# ExampleSerialClassForUrl. Or assign your class to Serial.

from pocs.tests.serial_handlers import NoOpSerial


def ExampleSerialClassForUrl(url):
    """Implementation of serial_class_for_url called by serial.serial_for_url.

    Returns the url, possibly modified, and a factory function to be called to
    create an instance of a SerialBase sub-class (or at least behaves like it).
    You can return a class as that factory function, as calling a class creates
    an instance of that class.

    serial.serial_for_url will call that factory function with None as the
    port parameter (the first), and after creating the instance will assign
    the url to the port property of the instance.

    Returns:
        A tuple (url, factory).
    """
    return url, Serial


# Assign to this global variable from a test to override this default behavior.
serial_class_for_url = ExampleSerialClassForUrl

# Or assign your own class to this global variable.
Serial = NoOpSerial
