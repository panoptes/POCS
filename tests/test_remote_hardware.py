from unittest.mock import patch

import astropy.units as u
import httpx
import pytest
import respx
from astropy.coordinates import EarthLocation

from panoptes.pocs.camera import create_cameras_from_config
from panoptes.pocs.camera.remote import Camera as RemoteCamera
from panoptes.pocs.mount import create_mount_from_config
from panoptes.pocs.mount.remote import Mount as RemoteMount
from panoptes.pocs.scheduler import create_scheduler_from_config
from panoptes.pocs.scheduler.remote import Scheduler as RemoteScheduler


@pytest.fixture
def location():
    return EarthLocation(lat=19.5 * u.deg, lon=-155.5 * u.deg, height=3400 * u.m)


@pytest.fixture(autouse=True)
def mock_config():
    with patch("panoptes.pocs.base.PanBase.get_config") as mock_get_config:

        def side_effect(key, default=None):
            config = {
                "directories.base": "/tmp",
                "directories.fields": "conf_files/fields",
                "directories.mounts": "resources/mounts",
                "mount.brand": "simulator",
                "mount.driver": "panoptes.pocs.mount.simulator",
                "mount.settings": {},
                "mount.serial.port": "/dev/FAKE",
                "simulator": ["all"],
            }
            return config.get(key, default)

        mock_get_config.side_effect = side_effect
        yield mock_get_config


@respx.mock
def test_remote_mount(location, respx_mock):
    url = "http://localhost:8001"
    respx_mock.post(f"{url}/connect").mock(return_value=httpx.Response(200, json={"result": True}))
    respx_mock.get(f"{url}/status").mock(
        return_value=httpx.Response(200, json={"result": {"is_connected": True}})
    )

    mount = RemoteMount(location=location, endpoint_url=url)
    assert mount.connect() is True
    status = mount.status
    assert status["result"]["is_connected"] is True


@respx.mock
def test_remote_camera(respx_mock):
    url = "http://localhost:8002"
    cam_name = "TestCam"
    respx_mock.get(f"{url}/TestCam/status").mock(
        return_value=httpx.Response(200, json={"result": {"is_connected": True, "temperature": 20.0}})
    )

    cam = RemoteCamera(name=cam_name, endpoint_url=url)
    assert cam.is_connected is True
    assert cam.temperature == 20.0


@respx.mock
def test_remote_scheduler(location, respx_mock):
    url = "http://localhost:8003"
    respx_mock.post(f"{url}/clear_available_observations").mock(
        return_value=httpx.Response(200, json={"result": True})
    )
    respx_mock.get(f"{url}/has_valid_observations").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    from astroplan import Observer

    observer = Observer(location=location)
    scheduler = RemoteScheduler(observer=observer, endpoint_url=url)
    assert scheduler.has_valid_observations is True


def test_create_remote_mount_from_config(location):
    mount_config = {
        "driver": "panoptes.pocs.mount.remote",
        "endpoint_url": "http://remote-mount:8001",
        "brand": "simulator",
    }
    mount = create_mount_from_config(mount_info=mount_config, earth_location=location)
    assert isinstance(mount, RemoteMount)
    assert mount.endpoint_url == "http://remote-mount:8001"


def test_create_remote_camera_from_config():
    camera_config = {
        "devices": [{"model": "remote", "name": "RemoteCam", "endpoint_url": "http://remote-camera:8002"}]
    }
    cameras = create_cameras_from_config(config=camera_config)
    assert "RemoteCam" in cameras
    assert isinstance(cameras["RemoteCam"], RemoteCamera)
    assert cameras["RemoteCam"].endpoint_url == "http://remote-camera:8002"


@patch("panoptes.pocs.scheduler.create_constraints_from_config", return_value=[])
@respx.mock
def test_create_remote_scheduler_from_config(mock_constraints, location, respx_mock):
    url = "http://remote-scheduler:8003"
    respx_mock.post(f"{url}/clear_available_observations").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    scheduler_config = {
        "type": "panoptes.pocs.scheduler.remote",
        "endpoint_url": url,
        "fields_file": "simple.yaml",
    }
    from astroplan import Observer

    observer = Observer(location=location)

    import os

    fields_path = "/tmp/conf_files/fields/simple.yaml"
    os.makedirs(os.path.dirname(fields_path), exist_ok=True)
    with open(fields_path, "w") as f:
        f.write("fields:\n  - name: TestField\n    coords: 00h00m00s +00d00m00s")

    scheduler = create_scheduler_from_config(config=scheduler_config, observer=observer)
    assert isinstance(scheduler, RemoteScheduler)
    assert scheduler.endpoint_url == url
