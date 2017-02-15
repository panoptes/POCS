from astropy import units as u
from pocs.scheduler.field import Field
from pocs.scheduler.observation import DitheredObservation
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

        if pocs.observatory.has_hdr_mode and isinstance(current_observation, DitheredObservation):

            pocs.logger.debug("Getting exposure times from imager array")

            min_magnitude = current_observation.extra_config.get('min_magnitude', 10) * u.ABmag
            max_magnitude = current_observation.extra_config.get('max_magnitude', 20) * u.ABmag
            max_exptime = current_observation.extra_config.get('max_exptime', 300) * u.second

            # Generating a list of exposure times for the imager array
            hdr_targets = hdr.get_hdr_target_list(imager_array=pocs.observatory.imager_array,
                                                  imager_name='canon_sbig_g',
                                                  coords=current_observation.field.coord,
                                                  name=current_observation.field.name,
                                                  minimum_magnitude=min_magnitude,
                                                  maximum_exptime=max_exptime,
                                                  maximum_magnitude=max_magnitude,
                                                  long_exposures=1,
                                                  factor=2,
                                                  dither_parameters={
                                                      'pattern_offset': 5 * u.arcmin,
                                                      'random_offset': 0.5 * u.arcmin,
                                                  }
                                                  )
            pocs.logger.debug("HDR Targets: {}".format(hdr_targets))

            fields = [Field(target['name'], target['position']) for target in hdr_targets]
            exp_times = [target['exp_time'][0] for target in hdr_targets]  # Not sure why exp_time is in tuple

            current_observation.field = fields
            current_observation.exp_time = exp_times

            pocs.logger.debug("New Dithered Observation: {}".format(current_observation))

        pocs.next_state = 'slewing'

    except Exception as e:
        pocs.logger.warning("Problem with preparing: {}".format())
