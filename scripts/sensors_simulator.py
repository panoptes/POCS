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

    def __init__(self, start_date=datetime.datetime(2015, 3, 1), delay=1.0):
        self.start_date = start_date
        self.delay = delay

        self.db = database.PanMongo()

    def run(self):
        """ Starts updating the "current" reading """
        self._cursor = self.db.sensors.find({
            "type": "environment",
            "computer_box": {"$exists": True},
            "camera_box": {"$exists": True},
            "time": {"$gte": self.start_date}
        })

        for record in self._cursor:
            self.db.sensors.update(
                {"status": "current", "type": "environment"},
                {"$set": {
                    "time": datetime.datetime.utcnow(),
                    "data": {
                        "camera_box": record["camera_box"],
                        "computer_box": record["computer_box"],
                    }
                } },
                True
            )

            print("Updated {}".format(record))
            time.sleep(self.delay)


if __name__ == "__main__":
    simulator = SensorSimulator()
    simulator.run()
