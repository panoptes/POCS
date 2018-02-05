from bson import json_util


def dumps(obj):
    """Dump an object to JSON.

    Args:
        obj (dict): An object to serialize.

    Returns:
        str: Serialized representation of object.
    """
    return json_util.dumps(obj)


def loads(msg):
    """Load an object from JSON.

    Args:
        msg (str): A serialized string representation of object.

    Returns:
        dict: The loaded object.
    """
    return json_util.loads(msg)


def dumps_file(fn, obj, clobber=False):
    """Convenience warpper to dump an object to a a file.

    Args:
        fn (str): Path of filename where object representation will be saved.
        obj (dict): An object to serialize.
        clobber (bool, optional): If object should be overwritten or appended to.
            Defaults to False, which will append to file.

    Returns:
        str: Filename of the file that was written to.
    """
    if clobber is True:
        mode = 'w'
    else:
        mode = 'a'

    with open(fn, mode) as f:
        f.write(dumps(obj) + "\n")

    return fn


def loads_file(file_path):
    """Convenience wrapper to load an object from a file.

    Args:
        file_path (str): Path of filename that contains a serialization of the
            the object.

    Returns:
        dict: The loaded object from the given file.
    """
    obj = None
    with open(file_path, 'r') as f:
        obj = loads(f.read())

    return obj
