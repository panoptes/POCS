import os
import yaml

from astropy import units as u
from pocs import hardware
from pocs.utils import listify
from warnings import warn


def load_config(config_files=None, simulator=None, parse=True, ignore_local=False):
    """ Load configuation information """

    # Default to the pocs.yaml file
    if config_files is None:
        config_files = ['pocs']
    config_files = listify(config_files)

    config = dict()

    config_dir = '{}/conf_files'.format(os.getenv('POCS'))

    for f in config_files:
        if not f.endswith('.yaml'):
            f = '{}.yaml'.format(f)

        if not f.startswith('/'):
            path = os.path.join(config_dir, f)
        else:
            path = f

        try:
            _add_to_conf(config, path)
        except Exception as e:
            warn("Problem with config file {}, skipping. {}".format(path, e))

        # Load local version of config
        if not ignore_local:
            local_version = os.path.join(config_dir, f.replace('.', '_local.'))
            if os.path.exists(local_version):
                try:
                    _add_to_conf(config, local_version)
                except Exception:
                    warn("Problem with local config file {}, skipping".format(local_version))

    if simulator is not None:
        config['simulator'] = hardware.get_simulator_names(simulator=simulator)

    if parse:
        config = parse_config(config)

    return config


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


def save_config(path, config, clobber=True):
    if not path.endswith('.yaml'):
        path = '{}.yaml'.format(path)

    if not path.startswith('/'):
        config_dir = '{}/conf_files'.format(os.getenv('POCS'))
        path = os.path.join(config_dir, path)

    if os.path.exists(path) and not clobber:
        warn("Path exists and clobber=False: {}".format(path))
    else:
        with open(path, 'w') as f:
            f.write(yaml.dump(config))


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None and isinstance(c, dict):
                config.update(c)
    except IOError:  # pragma: no cover
        pass
