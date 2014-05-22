import yaml
import os
import warnings

def load_config_file(filename):
	""" Sets a new config file """
	try:
		assert filename > ''
	except AssertionError as err:
		warnings.warn('Problem: {}'.format(err))

	# Set our new config file
	has_config._config_file = filename

	def decorator(Class):
		""" Simply calls existing decorator """
		return has_config(Class)
	
	return decorator

def has_config(Class):
	""" Class Decorator: Adds a config singleton to class """
    # If already read, simply return config
	if not has_config._config:
		load_config()

    # Add the config to the class
	if has_config._config:
		setattr(Class, 'config', has_config._config)

	return Class

def load_config(config=None, local_config=None):
	""" Loads the config from a file. If no file is specified, reloads default """
	if config is None:
		config = has_config._config_file

	if local_config is None:
		local_config = has_config._local_config_file		

	# Load the global config
	try:
	    with open(config, 'r') as f:
	        has_config._config.update(yaml.load(f.read()))
	except FileNotFoundError as err:
		warnings.warn('Problem: {}'.format(err))
	
	# If there is a local config load that
	try:		
	    with open(local_config, 'r') as f:
	        has_config._config.update(yaml.load(f.read()))	        
	except FileNotFoundError as err:
		pass

# This is global
has_config._config_file = '{}/../../config.yaml'.format(os.path.dirname(__file__))
has_config._local_config_file = '{}/../../config_local.yaml'.format(os.path.dirname(__file__))
has_config._config = dict()
