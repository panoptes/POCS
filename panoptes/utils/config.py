import yaml
import os
import warnings


def load_config():
    """ Returns the config information """

    # This is global
    _config_file = '{}/config.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _config = dict()

    # Load the global config
    try:
        with open(_config_file, 'r') as f:
            _config.update(yaml.load(f.read()))
    except IOError as err:
        warnings.warn('Cannot open config file. Please make sure $POCS environment variable is set: {}'.format(err))

    # If there is a local config load that
    try:
        with open(_local_config_file, 'r') as f:
            _config.update(yaml.load(f.read()))
    except IOError as err:
        pass

    return _config
