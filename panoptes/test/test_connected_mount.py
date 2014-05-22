import argparse
import importlib

import panoptes
import panoptes.mount as mount

parser = argparse.ArgumentParser()
parser.add_argument('mount', help='The mount type you would like to test')
args = parser.parse_args()

# Create the mount
module = importlib.import_module('.{}'.format(args.mount), 'panoptes.mount')
m = module.Mount()
m.connect()
m.logger.info("test_connected_mount")