from ...utils import current_time


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
    if observer.target_is_up(current_time(), target, observer.horizon):
        return (1, True)

    return (0, False)


def moon_separation(target, observer):
    # 10 degrees from moon

    moon_sep = target.coord.separation(observer.moon).value

    # This would potentially be within image
    if moon_sep < 15:
        return(0, False)

    return (moon_sep / 180, True)
