"""State: sleeping.

Terminal state after a night of observing. If safe conditions persist but
retry attempts are exhausted, stop the state loop; otherwise transition to
ready and reset the observing run.
"""

def on_enter(event_data):
    """Handle transition into the sleeping state."""
    pocs = event_data.model

    if pocs.is_safe() and pocs.should_retry is False:
        pocs.say("Weather is good and it is dark. Something must have gone wrong. Stopping loop.")
        pocs.stop_states()
    else:
        # Note: Unit will "sleep" before transition until it is safe to observe again.
        pocs.next_state = "ready"
        pocs.reset_observing_run()

    pocs.say("Another successful night!")
