from astropy import units as u
from pocs.utils import hdr


def on_enter(event_data):
    """Pointing State

    Take 30 second exposure and plate-solve to get the pointing error
    """
    pocs = event_data.model

    pocs.next_state = 'parking'

    try:
        pocs.say("Preparing the observations for our selected target")

        current_observation = pocs.observatory.current_observation

        if pocs.observatory.has_hdr_mode and current_observation.hdr_mode:

            pocs.logger.debug("Getting exposure times from imager array")

            min_magnitude = current_observation.extra_config.get('min_magnitude', 10) * u.ABmag
            max_magnitude = current_observation.extra_config.get('max_magnitude', 20) * u.ABmag
            max_exptime = current_observation.extra_config.get('max_exptime', 300) * u.second

            # Generating a list of exposure times for the imager array
            hdr_targets = hdr.get_hdr_target_list(imager_array=pocs.observatory.imager_array,
                                                  coords=current_observation.field.coord,
                                                  name=current_observation.field.name,
                                                  minimum_magnitude=min_magnitude,
                                                  maximum_exptime=max_exptime,
                                                  maximum_magnitude=max_magnitude,
                                                  num_longexp=1,
                                                  factor=2,
                                                  )
            pocs.logger.warning(hdr_targets)
            # pocs.say("Exposure times: {}".format(exp_times))
            # current_observation.exp_time = exp_times
            # current_observation.min_nexp = len(exp_times)
            # current_observation.exp_set_size = len(exp_times)

            pocs.next_state = 'slewing'

    except Exception as e:
        pocs.logger.warning("Problem with preparing: {}".format())
