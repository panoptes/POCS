from pymata_express import pymata_express

from panoptes.pocs.base import PanBase


class PowerBoard(PanBase):
    """Power distribution and monitoring"""

    def __init__(self, name='Power Board', arduino_instance_id=None, channels=None, pins=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = name

        # Lookup config for power board.
        self.config = self.get_config('environment.power')

        arduino_instance_id = arduino_instance_id or self.config.get('arduino_instance_id', default=1)
        self.channels = channels or self.config.get('channels', default=dict())

        # Get the pin mapping from the config if not provided.
        self.pin_mapping = pins or self.config.get('pins', default=dict())

        # Set up the PymataExpress board.
        self.logger.debug(f'Setting up Power board connection')
        self.board = pymata_express.PymataExpress(arduino_instance_id=arduino_instance_id)

        self.setup_pins()

        self.logger.success(f'Power board')

    def setup_pins(self, analog_pins=None, digital_pins=None, analog_read_callback=None):
        """Set the pin modes."""
        digital_pins = digital_pins or self.pin_mapping['digital']
        analog_pins = analog_pins or self.pin_mapping['analog']

        # Generic logging callback if none is provided.
        if analog_read_callback is None:
            def analog_callback(pin_type, pin_number, pin_value, raw_time_stamp):
                self.logger.trace(f'Analog read: {pin_type} {pin_number} {pin_value} {raw_time_stamp}')

            analog_read_callback = analog_callback

        self.logger.debug(f'Setting analog pin modes for {self.name}')
        for pin_number, label in analog_pins:
            self.board.set_pin_mode_analog_input(pin_number, callback=analog_read_callback)

        self.logger.debug(f'Setting digital pin modes for {self.name}')
