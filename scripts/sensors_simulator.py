#!/usr/bin/python3

import time
import datetime
import json
import bson.json_util as json_util
import pymongo

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from panoptes.utils import config, logger, serial, error, database


class SensorSimulator(object):

    """ Accepts a date and loops through mongodb values, updating current

    Args:
        start_date (datetime.datetime): Date to start from. Defaults to start of year.
        delay (int):                    Amount of time to delay between updates. Defaults
            to 1 sec
    """

    def __init__(self, start_date=datetime.datetime(2015, 3, 20), delay=1.0):
        self.start_date = start_date
        self.delay = delay

        self.db = database.PanMongo()

    def run(self):
        """ Starts updating the "current" reading """
        self._cursor = self.db.sensors.find({
            "type": "environment",
            "data.computer_box": {"$exists": True},
            "data.camera_box": {"$exists": True},
            "time": {"$gte": self.start_date}
        })

        print("Updating...", end="", flush=True)
        for record in self._cursor:
            self.db.sensors.update(
                {"status": "current", "type": "environment"},
                {"$set": {
                    "time": datetime.datetime.utcnow(),
                    "data": {
                        "camera_box": record["data"]["camera_box"],
                        "computer_box": record["data"]["computer_box"],
                    }
                } },
                True
            )

            print(".", end="", flush=True)
            time.sleep(self.delay)


if __name__ == "__main__":
    simulator = SensorSimulator()
    simulator.run()
