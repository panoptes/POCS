import os
import yaml


def load_config(simulator=[]):
    """ Returns the config information """
    _config = dict()

    # This is global
    _config_file = '{}/config.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _log_file = '{}/log.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))

    _add_to_conf(_config, _config_file)
    _add_to_conf(_config, _local_config_file)
    _add_to_conf(_config, _log_file)

    if len(simulator) > 0:
        _config['simulator'] = simulator

    return _config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            config.update(yaml.load(f.read()))
    except IOError:
        pass
