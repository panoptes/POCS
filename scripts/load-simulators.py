import time

from panoptes.pocs.mount import create_mount_simulator
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.core import POCS

pocs = POCS(Observatory(mount=create_mount_simulator(),
                        scheduler=create_scheduler_from_config(),
                        cameras=create_cameras_from_config(),
                        db_type='memory'),
            simulators=['dome', 'night', 'weather', 'power'])
time.sleep(1)
print(f'POCS simulator instance created as "pocs"')
