from unittest import TestCase

from samcli.lib.utils.arn_utils import InvalidArnValue, ARNParts


class TestArnUtils(TestCase):
    def test_invalid_arn_should_fail(self):
        with self.assertRaises(InvalidArnValue):
            _ = ARNParts("invalid_arn")

    def test_valid_arn(self):
        partition = "aws"
        service = "lambda"
        region = "us-east-1"
        account_id = "0123456789"
        resource_id = "resource_id"
        arn_value = f"arn:{partition}:{service}:{region}:{account_id}:{resource_id}"

        arn_parts = ARNParts(arn_value)

        self.assertEqual(arn_parts.partition, partition)
        self.assertEqual(arn_parts.service, service)
        self.assertEqual(arn_parts.region, region)
        self.assertEqual(arn_parts.account_id, account_id)
        self.assertEqual(arn_parts.resource_id, resource_id)
