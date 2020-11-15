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
        """Set the pin modes.

        Args:
            analog_pins (dict or None): Analog pin mapping. If not provided,
                uses 'analog' pins from `self.pin_mapping`.
            digital_pins (dict or None): Digital pin mapping. If not provided,
                uses 'digital' pins from `self.pin_mapping`.
            analog_read_callback (callable or None): A callback for the analog
                input pins. If not provided a default logging callback is used.
                Callback should accept a single list parameter, which will be
                populated with: pin_type, pin_number, pin_value, time_stamp.
        """
        digital_pins = digital_pins or self.pin_mapping['digital']
        analog_pins = analog_pins or self.pin_mapping['analog']

        # Generic logging callback if none is provided.
        if analog_read_callback is None:
            def analog_callback(data):
                pin_type, pin, value, time_stamp = data
                self.logger.trace(f'Analog read: {pin_type} {pin} {value} {time_stamp}')

            analog_read_callback = analog_callback

        self.logger.debug(f'Setting analog pins for {self.name}')
        for pin_number, label in analog_pins:
            self.logger.debug(f'Setting pin_number={pin_number} as analog input.')
            self.board.set_pin_mode_analog_input(pin_number, callback=analog_read_callback)

        # All our pins are output on PowerBoard.
        self.logger.debug(f'Setting digital pin for {self.name}')
        for pin_number, pin_config in digital_pins:
            pin_mode = pin_config['mode']
            pin_name = pin_config['name']
            initial_pin_state = pin_config['initial']

            self.logger.debug(f'Setting digital pin_number={pin_number} ({pin_name}) as {pin_mode}')
            self.board.set_pin_mode_digital_output(pin_number)

            # Set initial state on digital output pin.
            self.logger.debug(f'Setting digital output pin {pin_number} to {initial_pin_state}')
            self.board.digital_write(pin_number, initial_pin_state)

    def __str__(self):
        return f'Power Distribution Board - {self.name}'

    def __del__(self):
        self.board.shutdown()
