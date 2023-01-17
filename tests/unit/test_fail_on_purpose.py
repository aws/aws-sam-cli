from unittest import TestCase


class TestFailureOnPurpose(TestCase):
    def test_fail_on_purpose(self):
        self.fail()
