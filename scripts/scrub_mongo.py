#!/usr/bin/env python

import pymongo

client = pymongo.MongoClient()
db = client.panoptes.sensors

# Scrub data for various possible inputs
for i in range(5):
    for dev in ['arduino_', 'ttyACM']:
        key = "data./dev/{}{}".format(dev, i)

        # If it has an 'accelerometer' reading it is camera_box
        results = db.update_many(
            {"type": "environment", "{}.accelerometer".format(key): {"$exists": True}},
            {"$rename": {key: "data.camera_box", 'date': 'time'}}
        )
        print("{} Camera {}".format(key, results.modified_count))

        # If it has an 'voltage' reading it is computer
        results = db.update_many(
            {"type": "environment", "{}.voltages".format(key): {"$exists": True}},
            {"$rename": {key: "data.computer_box", 'date': 'time'}}
        )
        print("{} Computer {}".format(key, results.modified_count))
