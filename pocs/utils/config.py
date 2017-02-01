import os
import sys
import yaml

from astropy import units as u
from pocs.utils import listify
from warning import warn


def load_config(config_file, simulator=[]):
    """ Returns the config information """

    config = dict()

    config_files = listify(config_file)

    config_dir = '{}/conf_files'.format(os.getenv('POCS'))

    for f in config_files:
        f = '{}.yaml'.format(f)
        path = os.path.join(config_dir, f)

        try:
            _add_to_conf(config, path)
        except:
            warn("Problem with config file {}, skipping".format(path))

        local_version = os.path.join(config_dir, f.replace('.', '_local.'))
        if os.path.exists(local_version):
            _add_to_conf(config, local_version)

    if len(simulator) > 0:
        if 'all' in simulator:
            config['simulator'] = ['camera', 'mount', 'weather', 'night']
        else:
            config['simulator'] = simulator

    return parse_config(config)


def parse_config(config):
    # Add units to our location
    if 'location' in config:
        loc = config['location']

        for angle in ['latitude', 'longitude', 'horizon', 'twilight_horizon']:
            if angle in loc:
                loc[angle] = loc[angle] * u.degree

        loc['elevation'] = loc.get('elevation', 0) * u.meter

    # Prepend the base directory to relative dirs
    if 'directories' in config:
        base_dir = os.getenv('PANDIR')
        for dir_name, rel_dir in config['directories'].items():
            if not rel_dir.startswith('/'):
                config['directories'][dir_name] = '{}/{}'.format(base_dir, rel_dir)

    return config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None:
                config.update(c)
    except IOError:  # pragma: no cover
        pass
