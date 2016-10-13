import os
import sys
import yaml

from astropy import units as u


def load_config(simulator=[]):
    """ Returns the config information """
    _config = dict()

    # This is global
    _log_file = '{}/log.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    _config_file = '{}/config.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))

    if not os.path.exists(_config_file):
        sys.exit("Problem loading config file, check that it exists: {}".format(_config_file))

    _add_to_conf(_config, _config_file)
    _add_to_conf(_config, _log_file)

    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS', '/var/panoptes/POCS'))
    if os.path.exists(_local_config_file):
        _add_to_conf(_config, _local_config_file)

    if len(simulator) > 0:
        if 'all' in simulator:
            _config['simulator'] = ['camera', 'mount', 'weather', 'night']
        else:
            _config['simulator'] = simulator

    # Add units to our location
    if 'location' in _config:
        loc = _config['location']

        for angle in ['latitude', 'longitude', 'horizon', 'twilight_horizon']:
            if angle in loc:
                loc[angle] = loc[angle] * u.degree

        loc['elevation'] = loc.get('elevation', 0) * u.meter

    return _config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None:
                config.update(c)
    except IOError:  # pragma: no cover
        pass
