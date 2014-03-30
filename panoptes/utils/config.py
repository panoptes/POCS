import yaml
import warnings
import os

import panoptes.utils.error

panoptes_config = '{}/../../config.yaml'.format(os.path.dirname(__file__))

def has_config(Class):
	""" Class Decorator: Adds a config singleton to class """
    # If already read, simply return config
	if not has_config._config:
		load_config(config_file=panoptes_config)

    # Add the config to the class
	if has_config._config:
		setattr(Class, 'config', has_config._config)

	return Class

def load_config(refresh=False, config_file=panoptes_config):
	""" Loads the config from a file """
	if refresh or not has_config._config:
		try:
		    with open(config_file, 'r') as f:
		        has_config._config.update(yaml.load(f.read()))
		except FileNotFoundError as err:
			raise InvalidConfig("Config file not found: {}".format(config_file))

# This is global
has_config._config = dict()