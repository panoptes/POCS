from panoptes.camera import AbstractCamera
import panoptes.utils.logger as logger


@logger.set_log_level(level='debug')
@logger.has_logger
class Camera(AbstractCamera):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_serial_number(self):
        '''
        Gets the 'EOS Serial Number' property and populates the 
        self.serial_number property
        '''
        lines = self.get('/main/status/eosserialnumber')
        if re.match('Label: Serial Number', lines[0]) and re.match('Type: TEXT', lines[1]):
            MatchObj = re.match('Current:\s([\w\d]+)', lines[2])
            if MatchObj:
                self.serial_number = MatchObj.group(1)
                self.logger.debug('  Serial Number: {}'.format(self.serial_number))
        return self.serial_number        