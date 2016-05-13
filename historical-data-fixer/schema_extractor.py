#!/usr/bin/python

# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# The initial batch of sensor data was huge (1.7GB) and a bit messy
# This is my quick and dirty python script to aggregate all of the records into a schema for BigQuery

import sys
import json
import collections
import pprint

# filename = sys.argv[1]

# filename = "../cached_data/sensors_sample.json"
filename = "../cached_data/sensors_export_20151026.json"

print "processing " + filename

records_counter = 0
schema = {}

def flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def add_to_schema(data):
    rowtype = data['type']

    if rowtype not in schema:
        schema[rowtype] = {}

    flat_data = flatten(data)
    for key in flat_data:
        if key != "type":
            schema[rowtype][key] = 1


with open(filename, "r", 1) as file:
    for line in file:
        if records_counter % 10000 == 0:
            print "processed " + str(records_counter)

        data = json.loads(line)

        if 'type' not in data:
            # attempt to fingerprint the mystery record
            if 'data' in data and '/dev/ttyACM0' in data['data'] and 'humidity' in data['data']['/dev/ttyACM0']:
                data['type'] = "environment"
            else:
                print "type missing, and failed to recover this line " + line

        if data['type'] == "weather":
            add_to_schema(data)
        elif data['type'] == "aag_weather":
            # aag_weather should be weather
            data['type'] = "weather"
            add_to_schema(data)
        elif data['type'] == "environment":
            # another round of cleanup for environment: find all the arduino* and ttyacm* and make them camera or computer
            # computer has voltage, camera has accelerometer values

            # There should only be 2
            assert len(data['data'].keys()) <= 2, "only expected 0-2 keys, got %r" % len(data['data'].keys())

            new_data = {}
            for key in data['data']:
                if 'voltages' in data['data'][key]: # it's a computer
                    pass
                    new_data['computer_box'] = data['data'][key]
                elif 'accelerometer' in data['data'][key]: # it's a camera
                    pass
                    new_data['camera_box'] = data['data'][key]
                else: #unknown value, abort
                    assert False, "got unexpected data format %r" % data['data']

            # flatten and merge
            data.pop('data')
            data.update(new_data)

            add_to_schema(data)
        else:
            print "skipping unknown type " + data['type']

        records_counter += 1

print "done! processed " + str(records_counter) + " records"

pprint.pprint(schema)


