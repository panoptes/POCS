import yaml
import os

import panoptes.utils.error

def has_config(Class):
	""" Class Decorator: Adds a config singleton to class """
    # If already read, simply return config
	if not has_config._config:
		load_config()

    # Add the config to the class
	if has_config._config:
		setattr(Class, 'config', has_config._config)

	return Class

def load_config(refresh=False):
	""" Loads the config from a file """
	if refresh or not has_config._config:
		try:
		    with open(has_config._config_file, 'r') as f:
		        has_config._config.update(yaml.load(f.read()))
		except FileNotFoundError as err:
			raise InvalidConfig("Config file not found: {}".format(has_config._config_file))

def set_config_file(filename):
	""" Sets a new config file """
	try:
		assert filename gt ''
	except AssertionError as err:
		raise InvalidConfig('filename cannot be clank')
	finally:
		has_config._config_file = filename

# This is global
has_config._config = dict()
has_config._config_file = '{}/../../panoptes_config.yaml'.format(os.path.dirname(__file__))