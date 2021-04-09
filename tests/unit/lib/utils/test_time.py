import time
import datetime

from unittest import TestCase

from samcli.lib.utils.time import to_timestamp, timestamp_to_iso, parse_date, to_utc, utc_to_timestamp


class TestTimestampToIso(TestCase):
    def test_must_work_on_timestamp_with_milliseconds(self):
        timestamp = 1530882594123
        expected = "2018-07-06T13:09:54.123000"

        self.assertEqual(expected, timestamp_to_iso(timestamp))

    def test_must_ignore_float_microseconds(self):
        timestamp = 1530882594123.9876
        expected = "2018-07-06T13:09:54.123000"

        self.assertEqual(expected, timestamp_to_iso(timestamp))


class TestToTimestamp(TestCase):
    def test_must_convert_to_timestamp(self):
        date = datetime.datetime.utcfromtimestamp(1530882594.123)
        expected = 1530882594123

        self.assertEqual(expected, to_timestamp(date))

    def test_convert_utc_to_timestamp(self):
        timestamp = time.time()
        utc = datetime.datetime.utcfromtimestamp(timestamp)
        # compare in milliseconds
        self.assertEqual(int(timestamp * 1000), utc_to_timestamp(utc))


class TestToUtc(TestCase):
    def test_with_timezone(self):

        date = parse_date("2018-07-06 13:09:54 PDT")
        expected = datetime.datetime(2018, 7, 6, 20, 9, 54)

        result = to_utc(date)
        self.assertEqual(expected, result)

    def test_with_utc_timezone(self):

        date = parse_date("2018-07-06T13:09:54Z")
        expected = datetime.datetime(2018, 7, 6, 13, 9, 54)

        result = to_utc(date)
        self.assertEqual(expected, result)

    def test_without_timezone(self):

        date = parse_date("2018-07-06T13:09:54Z").replace(tzinfo=None)
        expected = datetime.datetime(2018, 7, 6, 13, 9, 54)

        result = to_utc(date)
        self.assertEqual(expected, result)


class TestParseDate(TestCase):
    def test_must_parse_date(self):
        date_str = "2018-07-06T13:09:54"
        expected = datetime.datetime(2018, 7, 6, 13, 9, 54)

        self.assertEqual(expected, parse_date(date_str))

    def test_must_parse_relative_time_in_utc(self):
        now = datetime.datetime.utcnow()
        date_str = "1hour ago"

        # Strip out microseconds & seconds since we only care about hours onwards
        expected = (now - datetime.timedelta(hours=1)).replace(microsecond=0, second=0)
        result = parse_date(date_str).replace(microsecond=0, second=0)

        self.assertEqual(expected, result)
