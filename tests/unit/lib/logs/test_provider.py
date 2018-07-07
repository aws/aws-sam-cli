
from unittest import TestCase

from samcli.lib.logs.provider import LogGroupProvider


class TestLogGroupProvider_for_lambda_function(TestCase):

    def test_must_return_log_group_name(self):
        expected = "/aws/lambda/myfunctionname"
        result = LogGroupProvider.for_lambda_function("myfunctionname")

        self.assertEquals(expected, result)
