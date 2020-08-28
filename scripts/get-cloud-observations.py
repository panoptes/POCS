#!/usr/bin/env python

"""Gets observations from PANOPTES Observation Portal [https://github.com/panoptes/panoptes-tom].

This Python script calls the 'get-cloud-observations' cloud function to
generate a list of observation targets from the portal.
This target list is then outputted to a YAML file.

Example:
python scripts/get-cloud-observations.py --targets-file resources/targets/simple_test.yaml \
     --facility PAN001 --overwrite

"""

import click
import yaml

import subprocess

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.serializers import from_json, to_json

logger = get_logger()


@click.command()
@click.option("--cloud-function-name", default="get-tom-observations")
@click.option("--targets-file", required=True, help="Output file for returned observations")
@click.option("--facility", required=True, help="Observation facility name (ie. PAN001)")
@click.option(
    "--overwrite", is_flag=True, help="Should targets file be appended to or overwritten."
)
def main(
    targets_file=None, facility=None, cloud_function_name="get-tom-observations", overwrite=False,
):
    # Convenience function for printing if verbose.
    logger.info(f"Calling {cloud_function_name}, writing new targets to {targets_file}")

    # Call the cloud function get json data.
    new_targets = call_cloud_function(cloud_function_name, facility)

    # Create targets.
    target_list = list()
    for target in new_targets:
        if target["facility"] == facility:
            logger.info(f"Adding {target}")
            # Pull out relevant fields.
            data = target["parameters"]

            ra = data.get("field_ra")
            dec = data.get("field_dec")
            position = f"{ra}deg {dec}deg"

            target_info = dict(
                name=data.get("name"),
                position=position,
                priority=data.get("priority", 100),
                exp_time=data.get("exp_time"),
                min_nexp=data.get("min_nexp"),
                exp_set_size=data.get("exp_set_size"),
            )

            target_list.append(target_info)

    # Write that to fields file.
    file_mode = "a"
    if overwrite:
        file_mode = "w"

    with open(targets_file, file_mode) as f:
        f.write(yaml.safe_dump(target_list, sort_keys=False))


def call_cloud_function(cloud_function_name, facility):
    request_info = to_json(dict(facility=facility))
    cmds = ["gcloud", "functions", "call", cloud_function_name, "--data", request_info]

    logger.info(f"Calling {cloud_function_name} with {cmds=}")

    completed_process = subprocess.run(cmds, check=True, capture_output=True)

    target_info = completed_process.stdout.decode().lstrip().rstrip().split("\n")
    new_targets = from_json(target_info[-1])

    return new_targets


if __name__ == "__main__":
    main()
