"""
Date & Time related utilities
"""

import datetime
import dateparser

from dateutil.tz import tzutc


def timestamp_to_iso(timestamp):
    """Convert Unix Epoch Timestamp to ISO formatted time string:
        Ex: 1234567890 -> 2018-07-05T03:09:43.842000

    Parameters
    ----------
    timestamp : int
        Unix epoch timestamp

    Returns
    -------


    """

    return to_datetime(timestamp).isoformat()


def to_datetime(timestamp):
    """Convert Unix Epoch Timestamp to Python's ``datetime.datetime`` object

    Parameters
    ----------
    timestamp : int
        Unix epoch timestamp

    Returns
    -------


    """

    timestamp_secs = int(timestamp) / 1000.0
    return datetime.datetime.utcfromtimestamp(timestamp_secs)


def to_timestamp(some_time):
    """Converts the given datetime value to Unix timestamp

    Parameters
    ----------
    some_time : datetime.datetime
        Value to be converted to unix epoch. This must be without any timezone identifier

    Returns
    -------


    """

    # `total_seconds()` returns elaped microseconds as a float. Get just milliseconds and discard the rest.
    return int((some_time - datetime.datetime(1970, 1, 1)).total_seconds() * 1000.0)


def utc_to_timestamp(utc):
    """Converts utc timestamp with tz_info set to utc to Unix timestamp

    Parameters
    ----------
    utc :
        datetime.datetime

    Returns
    -------
    type
        UNIX timestamp

    """

    return to_timestamp(utc.replace(tzinfo=None))


def to_utc(some_time):
    """Convert the given date to UTC, if the date contains a timezone.

    Parameters
    ----------
    some_time : datetime.datetime
        datetime object to convert to UTC

    Returns
    -------


    """

    # Convert timezone aware objects to UTC
    if some_time.tzinfo and some_time.utcoffset():
        some_time = some_time.astimezone(tzutc())

    # Now that time is UTC, simply remove the timezone component.
    return some_time.replace(tzinfo=None)


def parse_date(date_string):
    """Parse the given string as datetime object. This parser supports in almost any string formats.

    For relative times, like `10min ago`, this parser computes the actual time relative to current UTC time. This
    allows time to always be in UTC if an explicit time zone is not provided.

    Parameters
    ----------
    date_string : str
        String representing the date

    Returns
    -------


    """

    parser_settings = {
        # Relative times like '10m ago' must subtract from the current UTC time. Without this setting, dateparser
        # will use current local time as the base for subtraction, but falsely assume it is a UTC time. Therefore
        # the time that dateparser returns will be a `datetime` object that did not have any timezone information.
        # So be explicit to set the time to UTC.
        "RELATIVE_BASE": datetime.datetime.utcnow()
    }

    return dateparser.parse(date_string, settings=parser_settings)
