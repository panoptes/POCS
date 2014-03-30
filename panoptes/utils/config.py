import yaml
import warnings

def has_config(Class, refresh=False, config_file='panoptes_config.yaml'):
	""" Class Decorator: Adds a config singleton to class """

	if refresh:
		has_config._config = {}

    # If already read, simply return config
	if not has_config._config:
	    # If we haven't returned, we don't have a config so we read from file
		try:
		    with open(config_file, 'r') as f:
		        has_conifg._config = yaml.load(f.read())
		except FileNotFoundError as err:
			warnings.warn('{}'.format(err))

    # Add the config to the class
	if has_config._config:
		setattr(Class, 'config', has_config._config)

	return Class

# This is global
has_config._config = dict()
