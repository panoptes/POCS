"""State: slewing.

Command the mount to slew to the target coordinates and transition to
'pointing' when complete. If slewing fails, transition toward parking.
"""
from panoptes.pocs.utils import error


def on_enter(event_data):
    """Once inside the slewing state, set the mount slewing."""
    pocs = event_data.model
    try:
        if pocs.observatory.mount.is_parked:
            pocs.observatory.mount.unpark()

        # Wait until mount is_tracking, then transition to track state
        pocs.say("I'm slewing over to the coordinates to track the target.")

        # Start the mount slewing
        if pocs.observatory.mount.slew_to_target(blocking=True) is False:
            raise error.PocsError("Mount did not successfully slew to target.")

        pocs.say("I'm at the target, checking pointing.")
        pocs.next_state = "pointing"

    except Exception as e:
        pocs.say(f"Wait a minute, there was a problem slewing. Sending to parking. {e}")
