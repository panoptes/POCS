from astropy.time import Time

def observable(target, observatory):
    """Merit function to evaluate if a target is observable.
    Args:
        target (Target): Target object to evaluate.
        observatory (Observatory): The observatory object for which to evaluate
        the target.
    Returns:
        (1, observable): Returns 1 as the merit (a merit value of 1 indicates
        that all elevations are equally meritorious).  Will return True for
        observable if the target is observable or return Fale if not (which
        vetoes the target.
    """
    if observatory.target_is_up(Time.now(), target, observatory.horizon):
        return (1, True)

    return (0, False)
