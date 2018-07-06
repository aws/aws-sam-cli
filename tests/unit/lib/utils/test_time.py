
import datetime

from unittest import TestCase

from samcli.lib.utils.time import to_timestamp, timestamp_to_iso


class TestTimestampToIso(TestCase):

    def test_must_work_on_timestamp_with_milliseconds(self):
        timestamp = 1530882594123
        expected = "2018-07-06T13:09:54.123000"

        self.assertEquals(expected, timestamp_to_iso(timestamp))

    def test_must_ignore_float_microseconds(self):
        timestamp = 1530882594123.9876
        expected = "2018-07-06T13:09:54.123000"

        self.assertEquals(expected, timestamp_to_iso(timestamp))


class TestToTimestamp(TestCase):

    def test_must_(self):
        date = datetime.datetime.utcfromtimestamp(1530882594.123)
        expected = 1530882594123

        self.assertEquals(expected, to_timestamp(date))
