import os
import sys
import yaml

from astropy import units as u


def load_config(simulator=[], ignore_local=False):
    """ Returns the config information """
    _config = dict()

    # This is global
    _log_file = '{}/log.yaml'.format(os.getenv('POCS'))
    _config_file = '{}/config.yaml'.format(os.getenv('POCS'))

    if not os.path.exists(_config_file):
        sys.exit("Problem loading config file, check that it exists: {}".format(_config_file))

    _add_to_conf(_config, _config_file)
    _add_to_conf(_config, _log_file)

    _local_config_file = '{}/config_local.yaml'.format(os.getenv('POCS'))
    if os.path.exists(_local_config_file) and not ignore_local:
        _add_to_conf(_config, _local_config_file)

    if len(simulator) > 0:
        if 'all' in simulator:
            _config['simulator'] = ['camera', 'mount', 'weather', 'night']
        else:
            _config['simulator'] = simulator

    return parse_config(_config)


def parse_config(_config):
    # Add units to our location
    if 'location' in _config:
        loc = _config['location']

        for angle in ['latitude', 'longitude', 'horizon', 'twilight_horizon']:
            if angle in loc:
                loc[angle] = loc[angle] * u.degree

        loc['elevation'] = loc.get('elevation', 0) * u.meter

    # Prepend the base directory to relative dirs
    if 'directories' in _config:
        base_dir = os.getenv('PANDIR')
        for dir_name, rel_dir in _config['directories'].items():
            if not rel_dir.startswith('/'):
                _config['directories'][dir_name] = '{}/{}'.format(base_dir, rel_dir)

    return _config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None:
                config.update(c)
    except IOError:  # pragma: no cover
        pass
