"""State: ready.

System has initialized successfully; wait for safe/dark conditions and then
transition to 'scheduling' (or to 'parking' if dome open fails).
"""

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
                # TODO figure out how long until sunset and wait until then.
                wait_delay = 10 * 60  # 10 minutes
            else:
                wait_delay = pocs.get_config("wait_delay", default=180)  # seconds

            pocs.wait(delay=wait_delay)

        pocs.say("Ok, I'm all set up and ready to go!")
