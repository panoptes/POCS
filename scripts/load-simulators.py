import time

from panoptes.utils.config.server import config_server
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.core import POCS

print("Starting config-server")
conf_server = config_server('/POCS/conf_files/pocs.yaml')

pocs = POCS(Observatory(db_type='memory'), simulators=['all'])
time.sleep(1)
print(f'POCS simulator instance created as "pocs"')
