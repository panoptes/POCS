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


# copied from schema_extractor.py
# forked it so that it'll generate clean data that matches the hand edited schema I did in schema.txt

import sys
import json
import collections
import pprint

# filename = sys.argv[1]

#filename = "../cached_data/sensors_sample.json"
filename = "../cached_data/sensors_export_20151026.json"

# print "processing " + filename

records_counter = 0
schema = {}

default_values = {
    "unit_serial_number": "PAN001"
}
schema_mapping = {
    "_id_$oid": "oid",
    "time_$date": "timestamp",
    "date_$date": "timestamp",
    "data_Ambient Temperature": "ambient_temperature",
    "data_Ambient Temperature (C)": "ambient_temperature",
    "data_Device Name": "weather_sensor_name",
    "data_Device Serial Number": "weather_sensor_serial_number",
    "data_E1": "error_1",
    "data_E2": "error_2",
    "data_E3": "error_3",
    "data_E4": "error_4",
    "data_Errors_!E1": "error_1",
    "data_Errors_!E2": "error_2",
    "data_Errors_!E3": "error_3",
    "data_Errors_!E4": "error_4",
    "data_Firmware Version": "weather_sensor_firmware_version",
    "data_Gust Safe": "gust_safe",
    "data_Internal Voltage": "internal_voltage",
    "data_Internal Voltage (V)": "internal_voltage",
    "data_LDR Resistance": "ldr_resistance",
    "data_LDR Resistance (ohm)": "ldr_resistance",
    "data_PWM": "pwm_value",
    "data_PWM Value": "pwm_value",
    "data_Rain Frequency": "rain_frequency",
    "data_Rain Safe": "safe",
    "data_Rain Sensor Temp (C)": "rain_sensor_temperature",
    "data_Rain Sensor Temperature": "rain_sensor_temperature",
    "data_Safe": "sky_safe",
    "data_Sky Safe": "sky_safe",
    "data_Sky Temperature": "sky_temperature",
    "data_Sky Temperature (C)": "sky_temperature",
    "data_Switch": "switch",
    "data_Switch Status": "switch_status",
    "data_Wind Safe": "wind_safe",
    "data_Wind Speed": "wind_speed",
    "data_Wind Speed (km/h)": "wind_speed",
}

def flatten(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def remap_and_print(data):
    flat_data = flatten(data)

    defaulted_data = flat_data.copy()
    # set defaults
    for key in default_values:
        if key not in flat_data:
            defaulted_data[key] = default_values[key]

    # copy it back over to get ready for next pass
    flat_data = defaulted_data;

    # do remapping
    remapped_data = flat_data.copy()

    for key in flat_data:
        if key in schema_mapping:
            del remapped_data[key]
            remapped_data[schema_mapping[key]] = flat_data[key]

    # change timestmaps to seconds since epoch
    if "timestamp" in remapped_data:
        remapped_data["timestamp"] /= float(1000)

    print json.dumps(remapped_data)

# do the real work

with open(filename, "r", 1) as file:
    for line in file:
        # if records_counter % 10000 == 0:
            # print "processed " + str(records_counter)

        data = json.loads(line)

        if 'type' not in data:
            # attempt to fingerprint the mystery record
            if 'data' in data and '/dev/ttyACM0' in data['data'] and 'humidity' in data['data']['/dev/ttyACM0']:
                data['type'] = "environment"
            else:
                assert False, "type missing"
                # print "type missing, and failed to recover this line " + line

        if data['type'] == "weather":
            remap_and_print(data)
        elif data['type'] == "aag_weather":
            # aag_weather should be weather
            data['type'] = "weather"
            remap_and_print(data)
        elif data['type'] == "environment":
            # another round of cleanup for environment: find all the arduino* and ttyacm* and make them camera or computer
            # computer has voltage, camera has accelerometer values

            # There should only be 2
            assert len(data['data'].keys()) <= 2, "only expected 0-2 keys, got %r" % len(data['data'].keys())

            new_data = {}
            for key in data['data']:
                if 'voltages' in data['data'][key]: # it's a computer
                    new_data['computer_box'] = data['data'][key]
                elif 'accelerometer' in data['data'][key]: # it's a camera
                    new_data['camera_box'] = data['data'][key]
                else: #unknown value, abort
                    assert False, "got unexpected data format %r" % data['data']

            # flatten and merge
            data.pop('data')
            data.update(new_data)

            remap_and_print(data)
        else:
            assert False, "unknown record type"
            # print "skipping unknown type " + data['type']

        records_counter += 1

# print "done! processed " + str(records_counter) + " records"
pprint.pprint(schema)


