from pocs.camera.simulator import Camera
from pocs.camera.sdk import AbstractSDKDriver, AbstractSDKCamera


class SDKDriver(AbstractSDKDriver):
    def __init__(self, library_path=None, **kwargs):
        # Get library loader to load libc, which should usually be present...
        super().__init__(name='c', library_path=library_path, **kwargs)

    def get_SDK_version(self):
        return "Simulated SDK Driver v0.001"

    def get_cameras(self):
        cameras = {'SSC007': 'DEV_USB0',
                   'SSC101': 'DEV_USB1',
                   'SSC999': 'DEV_USB2'}
        return cameras


class Camera(AbstractSDKCamera, Camera):
    def __init__(self,
                 name='Simulated SDK camera',
                 driver=SDKDriver,
                 *args, **kwargs):
        super().__init__(name, driver, *args, **kwargs)
