import re
import time
from abc import ABC
from typing import Dict, List, Union

import gphoto2 as gp
from panoptes.utils import error
from panoptes.utils.images import cr2 as cr2_utils

from panoptes.pocs.camera import AbstractCamera

file_save_re = re.compile(r'Saving file as (.*)')


class AbstractGPhotoCamera(AbstractCamera, ABC):  # pragma: no cover
    """ Abstract camera class that uses gphoto2 interaction.
    Args:
        config(Dict):   Config key/value pairs, defaults to empty dict.
    """

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.gphoto2 = gp.Camera()
        self._properties = None
        self.logger.info(f'GPhoto2 camera {self.name} created on {self.port}')

        self.logger.debug(f"Connecting to camera on port {self.port}")
        try:
            # Get a list of available ports
            port_info_list = gp.check_result(gp.gp_port_info_list_new())
            gp.check_result(gp.gp_port_info_list_load(port_info_list))
            # Find the port index that matches the given port
            port_index = gp.check_result(gp.gp_port_info_list_lookup_path(port_info_list, self.port))
            # Get the port info
            port_info = gp.check_result(gp.gp_port_info_list_get_info(port_info_list, port_index))
            # Set the port info for the camera
            gp.check_result(self.gphoto2.set_port_info(port_info))
        except gp.GPhoto2Error as e:
            raise error.CameraNotFound(f"Camera not found on port {self.port}: {e}")

    @property
    def temperature(self):
        return None

    @property
    def target_temperature(self):
        return None

    @property
    def cooling_power(self):
        return None

    @AbstractCamera.uid.getter
    def uid(self) -> str:
        """ A six-digit serial number for the camera """
        return self._serial_number[0:6]

    def connect(self):
        """Connect to the camera.
        This will attempt to connect to the camera using gphoto2.
        """
        try:
            self.gphoto2.init()
            self._connected = True
            self.logger.info(f"GPhoto2 camera {self.name} connected on {self.port}")
        except gp.GPhoto2Error as e:
            raise error.CameraNotFound(f"Camera not found: {e}")

    @property
    def is_exposing(self):
        return self._is_exposing_event.is_set()

    def process_exposure(self, metadata, **kwargs):
        """Converts the CR2 to FITS then processes image."""
        # Wait for exposure to complete. Timeout handled by exposure thread.
        while self.is_exposing:
            time.sleep(0.5)

        metadata['filepath'] = metadata['filepath'].replace('.cr2', '.fits')
        super(AbstractGPhotoCamera, self).process_exposure(metadata, **kwargs)

    def set_property(self, prop: str, val: Union[str, int]):
        """ Set a property on the camera.
        Args:
            prop (str): The property to set.
            val (str or int): The value to set the property to.
        Raises:
            ValueError: If the property is not found.
        """
        self.logger.debug(f'Setting {prop=} to {val=}')
        try:
            config = self.gphoto2.get_config()
            widget = config.get_child_by_name(prop)
            widget.set_value(val)
            self.gphoto2.set_config(config)
        except gp.GPhoto2Error as e:
            raise error.InvalidCommand(f"Could not set property {prop} to {val}: {e}")

    def set_properties(self, prop2value: Dict[str, str] = None):
        """ Sets a number of properties all at once.
        Args:
            prop2value (dict or None): A dict with keys corresponding to the property to
                be set and values corresponding to the literal value.
        """
        if prop2value:
            for prop, val in prop2value.items():
                try:
                    self.set_property(prop, val)
                except Exception:
                    self.logger.debug(f'Skipping {prop=} {val=}')

    def get_property(self, prop: str) -> str:
        """ Gets a property from the camera """
        try:
            config = self.gphoto2.get_config()
            widget = config.get_child_by_name(prop)
            return widget.get_value()
        except gp.GPhoto2Error as e:
            raise error.InvalidCommand(f"Could not get property {prop}: {e}")

    def load_properties(self) -> dict:
        """ Load properties from the camera.
        Reads all the configuration properties available via gphoto2 and returns
        as dictionary.
        """
        if self._properties is None:
            self.logger.debug('Getting all properties for gphoto2 camera')
            properties = {}
            try:
                config = self.gphoto2.get_config()
                for section in config.get_children():
                    for child in section.get_children():
                        properties[child.get_name()] = {
                            'label': child.get_label(),
                            'value': child.get_value(),
                            'type': child.get_type(),
                            'readonly': child.get_readonly(),
                        }
                        if child.get_type() == gp.GP_WIDGET_RADIO:
                            properties[child.get_name()]['choices'] = [c for c in child.get_choices()]

            except gp.GPhoto2Error as e:
                self.logger.warning(f'Could not load properties: {e!r}')

            self._properties = properties

        return self._properties

    def _poll_exposure(self, readout_args, exposure_time, timeout=None, interval=0.01):
        """Check the command output from gphoto2 for polling.
        This will essentially block until the camera is done exposing, which means
        the super call should not have to wait.
        """
        try:
            self.logger.debug(f'Waiting for capture to complete for {self}')
            # This blocks until the capture is complete.
            event_type, event_data = self.gphoto2.wait_for_event(int(timeout))
            if event_type == gp.GP_EVENT_FILE_ADDED:
                cam_file = self.gphoto2.file_get(
                    event_data.folder, event_data.name, gp.GP_FILE_TYPE_NORMAL)
                target_path = readout_args[0]
                self.logger.debug(f'Saving image to {target_path}')
                cam_file.save(target_path)
                self._readout(*readout_args)
            else:
                raise error.PanError(f'Unexpected event type: {event_type}')

        except Exception as err:
            self.logger.error(f"Error during readout on {self}: {err!r}")
            self._exposure_error = repr(err)
            raise err
        finally:
            self._is_exposing_event.clear()
            self.logger.debug(f'Exposing event cleared for {self}')

    def _readout(self, filename, headers, *args, **kwargs):
        self.logger.debug(f'Reading Canon DSLR exposure for {filename=}')
        try:
            self.logger.debug(f"Converting CR2 -> FITS: {filename}")
            cr2_utils.cr2_to_fits(filename, headers=headers, remove_cr2=False)
        except TimeoutError:
            self.logger.error(f'Error processing exposure for {filename} on {self}')
        finally:
            self._readout_complete = True

    def _set_target_temperature(self, target):
        return None

    def _set_cooling_enabled(self, enable):
        return None

    @classmethod
    def start_tether(cls, port: str, filename_pattern: str = '%Y%m%dT%H%M%S.%C'):
        """Start a tether for gphoto2 auto-download on given port using filename pattern."""
        print(f'Starting gphoto2 tether for {port=} using {filename_pattern=}')

        camera = gp.Camera()
        try:
            camera.init()
            print(f'gphoto2 tether started on {port=}')
            for event_type, event_data in camera.wait_for_event(1000 * 60 * 60):  # 1 hour
                if event_type == gp.GP_EVENT_FILE_ADDED:
                    cam_file = camera.file_get(
                        event_data.folder, event_data.name, gp.GP_FILE_TYPE_NORMAL)
                    target_path = filename_pattern
                    print(f'Saving image to {target_path}')
                    cam_file.save(target_path)
        except gp.GPhoto2Error as e:
            print(f'Error during tether: {e}')
        except KeyboardInterrupt:
            print(f'Stopping tether on {port=}')
        finally:
            camera.exit()

    @classmethod
    def gphoto_file_download(
        cls,
        port: str,
        filename_pattern: str,
        only_new: bool = True
    ):
        """Downloads (newer) files from the camera on the given port using the filename pattern."""
        print(f'Starting gphoto2 download for {port=} using {filename_pattern=}')
        camera = gp.Camera()
        filenames = []
        try:
            camera.init()
            files = camera.folder_list_files('/')
            for i, (name, value) in enumerate(files):
                if only_new:
                    # This is not a perfect way to check for new files, but it's a start.
                    # A better way would be to keep track of the last downloaded file.
                    # For now, we'll just download everything.
                    pass
                target_path = filename_pattern.format(i)
                print(f'Downloading {name} to {target_path}')
                cam_file = camera.file_get('/', name, gp.GP_FILE_TYPE_NORMAL)
                cam_file.save(target_path)
                filenames.append(target_path)
        except gp.GPhoto2Error as e:
            print(f'Error during file download: {e}')
        finally:
            camera.exit()

        return filenames
