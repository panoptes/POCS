from panoptes.utils.config import load_config as load_panoptes_config
from pocs import hardware


def load_config(*args, **kwargs):
    """Load config and check simulator.

    Args:
        *args: Passed to `panoptes.utils.config.load_config`.
        **kwargs: Passed to `panoptes.utils.config.load_config`.

    Returns:
        dict: A dictonary of config items w/ simulators added.
    """
    conf = load_panoptes_config(*args, **kwargs)

    simulator = kwargs.get('simulator', None)

    if simulator is not None:
        conf['simulator'] = hardware.get_simulator_names(simulator=simulator)

    return conf
