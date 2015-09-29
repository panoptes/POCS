from astropy.time import Time

def observable(target, observer):
    """Merit function to evaluate if a target is observable.
    Args:
        target (Target): Target object to evaluate.
        observer (Observatory): The observer object for which to evaluate
        the target.
    Returns:
        (1, observable): Returns 1 as the merit (a merit value of 1 indicates
        that all elevations are equally meritorious).  Will return True for
        observable if the target is observable or return Fale if not (which
        vetoes the target.
    """
    if observer.target_is_up(Time.now(), target, observer.horizon):
        return (1, True)

    return (0, False)
