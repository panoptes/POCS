import os
import sys
import yaml


def load_config():
    """ Returns the config information """
    _config = dict()

    # This is global
    _config_file = '{}/config.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))

    if not os.path.exists(_config_file):
        sys.exit("Problem loading config file, check that it exists: {}".format(_config_file))

    _add_to_conf(_config, _config_file)

    if os.path.exists(_local_config_file):
        _add_to_conf(_config, _local_config_file)

    return _config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None:
                config.update(c)
    except IOError:  # pragma: no cover
        pass
