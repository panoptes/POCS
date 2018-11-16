import os
import yaml
from contextlib import suppress

from astropy import units as u
from pocs import hardware
from pocs.utils import listify
from warnings import warn


def load_config(config_files=None, simulator=None, parse=True, ignore_local=False):
    """Load configuation information

    This function supports loading of a number of different files. If no options
    are passed to `config_files` then the default `$POCS/conf_files/pocs.yaml`
    will be loaded. See Notes for additional information.

    Notes:
        The `config_files` parameter supports a number of options:
        * `config_files` is a list and loaded in order, so the first entry
            will have any values overwritten by similarly named keys in
            the second entry.
        * Entries can be placed in the `$POCS/conf_files` folder and
            should be passed as just the file name, e.g.
            [`weather.yaml`, `email.yaml`] for loading
            `$POCS/conf_files/weather.yaml` and `$POCS/conf_files/email.yaml`
        * The `.yaml` extension will be added if not present, so list can
            be written as just ['weather', 'email'].
        * `config_files` can also be specified by an absolute path, which
            can exist anywhere on the filesystem.
        * Local versions of files can override built-in versions and are
            automatically loaded if placed in the `$POCS/conf_files` folder.
            The files have a `<>_local.yaml` name, where `<>` is the built-in
            file. So a `$POCS/conf_files/pocs_local.yaml` will override any
            setting in the default `pocs.yaml` file.
        * Local files can be ignored (mostly for testing purposes) with the
            `ignore_local` parameter.

    Args:
        config_files (list, optional): A list of files to load as config,
            see Notes for details of how to specify files.
        simulator (list, optional): A list of hardware items that should be
            used as a simulator.
        parse (bool, optional): If the config file should attempt to create
            objects such as dates, astropy units, etc.
        ignore_local (bool, optional): If local files should be ignored, see
            Notes for details.

    Returns:
        dict: A dictionary of config items
    """

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
        config = _parse_config(config)

    return config


def save_config(path, config, overwrite=True):
    """Save config to yaml file

    Args:
        path (str): Path to save, can be relative or absolute. See Notes
            in `load_config`.
        config (dict): Config to save.
        overwrite (bool, optional): True if file should be updated, False
            to generate a warning for existing config. Defaults to True
            for updates.
    """
    if not path.endswith('.yaml'):
        path = '{}.yaml'.format(path)

    if not path.startswith('/'):
        config_dir = '{}/conf_files'.format(os.getenv('POCS'))
        path = os.path.join(config_dir, path)

    if os.path.exists(path) and not overwrite:
        warn("Path exists and overwrite=False: {}".format(path))
    else:
        with open(path, 'w') as f:
            f.write(yaml.dump(config))


def _parse_config(config):
    # Add units to our location
    if 'location' in config:
        loc = config['location']

        for angle in [
            'latitude',
            'longitude',
            'horizon',
            'flat_horizon',
            'focus_horizon',
            'observe_horizon'
        ]:
            with suppress(KeyError):
                loc[angle] = loc[angle] * u.degree

        loc['elevation'] = loc.get('elevation', 0) * u.meter

    # Prepend the base directory to relative dirs
    if 'directories' in config:
        base_dir = os.getenv('PANDIR')
        for dir_name, rel_dir in config['directories'].items():
            abs_dir = os.path.normpath(os.path.join(base_dir, rel_dir))
            if abs_dir != rel_dir:
                config['directories'][dir_name] = abs_dir

    return config


def _add_to_conf(config, fn):
    try:
        with open(fn, 'r') as f:
            c = yaml.load(f.read())
            if c is not None and isinstance(c, dict):
                config.update(c)
    except IOError:  # pragma: no cover
        pass
