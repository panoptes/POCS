import os
import yaml


def load_config(self, fn='config.yaml'):
    config = dict()
    try:
        path = '{}/{}'.format(os.getenv('PEAS', '/var/panoptes/PEAS'), fn)
        with open(path, 'r') as f:
            config = yaml.load(f.read())
    except IOError:
        pass

    return config
