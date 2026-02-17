"""State: ready.

System has initialized successfully; wait for safe/dark conditions and then
transition to 'scheduling' (or to 'parking' if dome open fails).
"""

from astropy import units as u
from panoptes.utils.time import current_time


def on_enter(event_data):
    """
    Once in the `ready` state our unit has been initialized successfully. The next step is to
    schedule something for the night.
    """
    pocs = event_data.model

    if pocs.observatory.has_dome and not pocs.observatory.open_dome():
        pocs.say("Failed to open the dome while entering state 'ready'")
        pocs.logger.error("Failed to open the dome while entering state 'ready'")
        pocs.next_state = "parking"
    else:
        pocs.next_state = "scheduling"

        # Wait until it's safe to proceed.
        # TODO separate check for disk space, which will never break this loop.
        disk_space_checks = ["free_space_root", "free_space_images"]
        while pocs.is_safe(park_if_not_safe=False, ignore=disk_space_checks) is False:
            if pocs.is_dark() is False:
                # Calculate time until next evening astronomical twilight
                wait_delay = _calculate_wait_until_dark(pocs)
            else:
                wait_delay = pocs.get_config("wait_delay", default=180)  # seconds

            pocs.wait(delay=wait_delay)

        pocs.say("Ok, I'm all set up and ready to go!")


def _calculate_wait_until_dark(pocs):
    """Calculate how long to wait until evening astronomical twilight.

    During daytime, instead of waiting just 10 minutes, calculate the time until
    the next evening astronomical twilight and sleep for most of that duration
    (with a safety buffer to avoid overshooting).

    Args:
        pocs: The POCS instance with observatory information.

    Returns:
        float: Number of seconds to wait.
    """
    now = current_time()
    observer = pocs.observatory.observer

    # Get the next evening astronomical twilight time (when observing can start)
    next_twilight = observer.twilight_evening_astronomical(now, which="next")

    # Calculate time until twilight in seconds
    time_until_twilight = (next_twilight - now).to(u.second).value

    # Use a safety buffer to avoid sleeping right up to twilight
    # We wake up 10 minutes before to ensure we're ready
    safety_buffer = 10 * 60  # 10 minutes

    # Minimum wait time to avoid too-frequent checks
    min_wait = 5 * 60  # 5 minutes

    # Calculate actual wait time: sleep until shortly before twilight
    wait_time = max(min_wait, time_until_twilight - safety_buffer)

    # Log the calculated wait time for visibility
    hours = wait_time / 3600
    pocs.logger.info(
        f"Daytime sleep: waiting {wait_time:.0f}s ({hours:.1f}h) until "
        f"evening twilight at {next_twilight.iso}"
    )

    return wait_time
