from panoptes.pocs.core import POCS
from panoptes.pocs.observatory import Observatory
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.scheduler import create_scheduler_from_config


def create_pocs(simulators=None):
    scheduler = create_scheduler_from_config()
    mount = create_mount_from_config()
    cameras = create_cameras_from_config()

    observatory = Observatory(cameras=cameras, mount=mount, scheduler=scheduler)

    # Add simulators if necessary before running.
    pocs = POCS(observatory, simulators=simulators or list())
    return pocs
