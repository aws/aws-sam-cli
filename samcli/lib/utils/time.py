
import datetime


def timestamp_to_iso(timestamp):
    """
    Convert Unix Epoch Timestamp to ISO formatted time string:
        Ex: 1234567890 -> 2018-07-05T03:09:43.842000

    Parameters
    ----------
    timestamp : int
        Unix epoch timestamp

    Returns
    -------
    str
        ISO formatted time string
    """

    timestamp_secs = int(timestamp) / 1000
    return datetime.datetime.utcfromtimestamp(timestamp_secs).isoformat()


def to_timestamp(some_time):
    """
    Converts the given datetime value to Unix timestamp

    Parameters
    ----------
    some_time : datetime.datetime
        Value to be converted to unix epoch. This must be without any timezone identifier

    Returns
    -------
    int
        Unix timestamp of the given time
    """

    # `total_seconds()` returns elaped microseconds as a float. Get just milliseconds and discard the rest.
    return int((some_time - datetime.datetime(1970, 1, 1)).total_seconds() * 1000.0)
