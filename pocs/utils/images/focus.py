import numpy as np


def focus_metric(data, merit_function='vollath_F4', **kwargs):
    """Compute the focus metric.

    Computes a focus metric on the given data using a supplied merit function.
    The merit function can be passed either as the name of the function (must be
    defined in this module) or as a callable object. Additional keyword arguments
    for the merit function can be passed as keyword arguments to this function.

    Args:
        data (numpy array) -- 2D array to calculate the focus metric for.
        merit_function (str/callable) -- Name of merit function (if in
            pocs.utils.images) or a callable object.

    Returns:
        scalar: result of calling merit function on data
    """
    if isinstance(merit_function, str):
        try:
            merit_function = globals()[merit_function]
        except KeyError:
            raise KeyError(
                "Focus merit function '{}' not found in pocs.utils.images!".format(merit_function))

    return merit_function(data, **kwargs)


def vollath_F4(data, axis=None):
    """Compute F4 focus metric

    Computes the F_4 focus metric as defined by Vollath (1998) for the given 2D
    numpy array. The metric can be computed in the y axis, x axis, or the mean of
    the two (default).

    Arguments:
        data (numpy array) -- 2D array to calculate F4 on.
        axis (str, optional, default None) -- Which axis to calculate F4 in. Can
            be 'Y'/'y', 'X'/'x' or None, which will calculate the F4 value for
            both axes and return the mean.

    Returns:
        float64: Calculated F4 value for y, x axis or both
    """
    if axis == 'Y' or axis == 'y':
        return _vollath_F4_y(data)
    elif axis == 'X' or axis == 'x':
        return _vollath_F4_x(data)
    elif not axis:
        return (_vollath_F4_y(data) + _vollath_F4_x(data)) / 2
    else:
        raise ValueError(
            "axis must be one of 'Y', 'y', 'X', 'x' or None, got {}!".format(axis))


def mask_saturated(data, saturation_level=None, threshold=0.9, dtype=np.float64):
    if not saturation_level:
        try:
            # If data is an integer type use iinfo to compute machine limits
            dtype_info = np.iinfo(data.dtype)
        except ValueError:
            # Not an integer type. Assume for now we have 16 bit data
            saturation_level = threshold * (2**16 - 1)
        else:
            # Data is an integer type, set saturation level at specified fraction of
            # max value for the type
            saturation_level = threshold * dtype_info.max

    # Convert data to masked array of requested dtype, mask values above saturation level
    return np.ma.array(data, mask=(data > saturation_level), dtype=dtype)


def _vollath_F4_y(data):
    A1 = (data[1:] * data[:-1]).mean()
    A2 = (data[2:] * data[:-2]).mean()
    return A1 - A2


def _vollath_F4_x(data):
    A1 = (data[:, 1:] * data[:, :-1]).mean()
    A2 = (data[:, 2:] * data[:, :-2]).mean()
    return A1 - A2
