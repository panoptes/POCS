"""The protocol_*.py files in this package are based on PySerial's file
test/handlers/protocol_test.py, modified for different behaviors. The call
 serial.serial_for_url("XYZ://") looks for a class Serial in a file named protocol_XYZ.py in this
package (i.e. directory).

This package init file will be loaded as part of searching for a protocol handler in this package.
It is important to use root-relative imports (e.g. relative to the POCS directory) so that all
modules and packages are loaded only once.
"""
