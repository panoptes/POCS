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
from astroplan import Observer

from panoptes.pocs.utils.logger import get_logger
from panoptes.utils.serializers import from_json, to_json, to_yaml, from_yaml
from panoptes.pocs.scheduler import BaseScheduler

logger = get_logger()


@click.command()
@click.option("--cloud-function-name", default="get-tom-observations")
@click.option("--targets-file", required=True, help="Output file for returned observations")
@click.option("--facility", required=True, help="Observation facility name (ie. PAN001)")
@click.option(
    "--overwrite", is_flag=True, help="Should targets file be appended to or overwritten, default False"
)
def main(
    targets_file=None, facility=None, cloud_function_name="get-tom-observations", overwrite=False,
):
    # Convenience function for printing if verbose.
    logger.info(f"Calling {cloud_function_name}, writing new targets to {targets_file}")

    # Call the cloud function get json data.
    new_targets = call_cloud_function(cloud_function_name, facility)
     
    # Create a dummy scheduler to test adding files.
    dummy_observer = Observer.at_site("Subaru")
    test_scheduler = BaseScheduler(dummy_observer)

    # Create targets.
    target_list = list()
    for target in new_targets:
        if target["facility"] == facility:
            logger.info(f"Adding {target}")
            
          # Pull out relevant fields.
            data = target["parameters"]
               
            target_name = data.get("name")
            ra = data.get("field_ra")
            dec = data.get("field_dec")
            position = f"{ra}deg {dec}deg"
               
            exptime = data.get("exp_time")

            target_info = dict(
                name=target_name,
                position=position,
                priority=data.get("priority", 100),
                exptime=exptime,
                min_nexp=data.get("min_nexp"),
                exp_set_size=data.get("exp_set_size"),
            )
          
            try:
                test_scheduler.add_observation(target_info)
                target_list.append(target_info)
            except Exception as e:
                logger.warning(f'Cannot add observation: {target_info=} {e!r}')
            finally:
                logger.debug(f'Added {target_name} at {position=}')

    # Write that to fields file.
    file_mode = "a"
    if overwrite:
        file_mode = "w"

    try:
         with open(targets_file, file_mode) as f:
             to_yaml(target_list, stream=f)
             logger.success(f'Added {len(target_list) targets to {targets_file}}')
    except OSError as e:
         logger.error(e)


def call_cloud_function(cloud_function_name, facility):
    request_info = to_json(dict(facility=facility))
    # at top of file
    import shutil
    ...
    gcloud_cmd = shutil.which('gcloud')
    if gcloud_cmd is None:
        logger.error(f"gcloud command not found on system, can't get observations from the network")
    
    cmds = [gcloud_cmd, "functions", "call", cloud_function_name, "--data", request_info]

    logger.info(f"Calling {cloud_function_name} with {cmds=}")

    completed_process = subprocess.run(cmds, check=True, capture_output=True)

    # Get the targets as the last item from the gcloud output.
    target_info = completed_process.stdout.decode().strip().split("\n")[-1]
    new_targets = from_json(target_info)

    return new_targets


if __name__ == "__main__":
    main()
