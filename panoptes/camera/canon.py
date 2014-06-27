from panoptes.camera import AbstractCamera
import panoptes.utils.logger as logger


@logger.set_log_level(level='debug')
@logger.has_logger
class Camera(AbstractCamera):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)