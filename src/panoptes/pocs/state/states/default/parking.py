"""State: parking.

Transition to safely park the system: clear current observation context, close
the dome if present, and command the mount to park, then proceed to 'parked'.
"""


def on_enter(event_data):
    """Handle transition into the parking state."""
    pocs = event_data.model

    # Stop the telemetry run for the current observation (if one is active).
    try:
        pocs.db.stop_run()
        pocs.logger.debug("Telemetry run stopped")
    except Exception as e:
        pocs.logger.warning(f"Unable to stop telemetry run: {e!r}")

    # Clear any current observation
    pocs.observatory.current_observation = None
    pocs.observatory.current_offset_info = None

    pocs.next_state = "parked"

    if pocs.observatory.has_dome:
        pocs.say("Closing dome")
        if not pocs.observatory.close_dome():
            pocs.logger.critical("Unable to close dome!")
            pocs.say("Unable to close dome!")

    pocs.say("Ok, let's park!")
    pocs.observatory.mount.park()
