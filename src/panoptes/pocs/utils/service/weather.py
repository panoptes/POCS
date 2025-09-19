"""FastAPI service exposing weather station status and configuration.

This module wires up a FastAPI app with a lifespan hook that connects to the
weather station and periodically records readings. Two simple endpoints expose
current status and the active configuration.
"""
import os
import time
from contextlib import asynccontextmanager, suppress
from threading import Thread

from fastapi import FastAPI
from panoptes.utils.config.client import get_config
from serial.tools.list_ports import comports as get_comports

from panoptes.pocs.sensor.weather import WeatherStation

app_objects = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager for the lifespan of the app.

    This will connect to the weather station and record
    readings at a regular interval.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    conf = get_config("environment.weather", {})
    app_objects["conf"] = conf

    # Get list of possible ports for auto-detect or use the configured port.
    if conf.get("auto_detect", False) is True:
        ports = [p.device for p in get_comports()]
    else:
        ports = [conf["serial_port"]]

    # Check the ioptron symlink and skip that port if it exists.
    ioptron_port = None
    with suppress(FileNotFoundError):
        ioptron_port = os.readlink("/dev/ioptron")

    weather_thread: Thread = None

    # Try to connect to the weather station.
    for port in ports:
        if "ttyUSB" not in port and "weather" not in port:
            continue

        if port == ioptron_port:
            continue

        conf["serial_port"] = port
        try:
            weather_station = WeatherStation(**conf)
            weather_station.logger.info(f"Weather station setup: {weather_station}")

            def record_readings():
                """Record the current readings in the db."""
                record_interval = conf.get("record_interval", 60)
                weather_station.logger.info(f"Setting up weather recording {record_interval=}")
                while True:
                    time.sleep(record_interval)
                    try:
                        weather_station.record()
                    except Exception as e:
                        weather_station.logger.warning(f"Could not get weather record: {e}")

            # Create a thread to record the readings at an interval
            weather_thread = Thread(target=record_readings)
            weather_thread.daemon = True
            weather_thread.start()

            app_objects["weather_station"] = weather_station
            break
        except Exception as e:
            print(f"Could not connect to weather station on {port}: {e}")
    else:
        raise RuntimeError("Could not connect to weather station.")

    yield
    weather_station.logger.info("Shutting down weather station, please wait")
    weather_thread.join()


app = FastAPI(lifespan=lifespan)


@app.get("/status")
async def status():
    """Returns the power board status."""
    return app_objects["weather_station"].status


@app.get("/config")
async def get_ws_config():
    """Returns the power board status."""
    return app_objects["weather_station"]
