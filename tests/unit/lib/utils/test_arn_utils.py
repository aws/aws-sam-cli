from unittest import TestCase
from parameterized import parameterized

from samcli.lib.utils.arn_utils import InvalidArnValue, ARNParts


class TestArnUtils(TestCase):
    def test_invalid_arn_should_fail(self):
        with self.assertRaises(InvalidArnValue):
            _ = ARNParts("invalid_arn")

    @parameterized.expand(
        [
            (
                "arn:aws:service:region:account-id:resource-id",
                {
                    "partition": "aws",
                    "service": "service",
                    "region": "region",
                    "account_id": "account-id",
                    "resource_type": "",
                    "resource_id": "resource-id",
                },
            ),
            (
                "arn:aws:service:region:account-id:resource-type/resource-id",
                {
                    "partition": "aws",
                    "service": "service",
                    "region": "region",
                    "account_id": "account-id",
                    "resource_type": "resource-type",
                    "resource_id": "resource-id",
                },
            ),
            (
                "arn:aws:service:region:account-id:resource-type:resource-id",
                {
                    "partition": "aws",
                    "service": "service",
                    "region": "region",
                    "account_id": "account-id",
                    "resource_type": "resource-type",
                    "resource_id": "resource-id",
                },
            ),
            (
                "arn:partition:service:region:account-id:repository/repository-name",
                {
                    "partition": "partition",
                    "service": "service",
                    "region": "region",
                    "account_id": "account-id",
                    "resource_type": "repository",
                    "resource_id": "repository-name",
                },
            ),
            (
                "arn:partition:service:region:account-id:s3-bucket-name",
                {
                    "partition": "partition",
                    "service": "service",
                    "region": "region",
                    "account_id": "account-id",
                    "resource_type": "",
                    "resource_id": "s3-bucket-name",
                },
            ),
            (
                "arn:partition:service:::s3-bucket-name",
                {
                    "partition": "partition",
                    "service": "service",
                    "region": "",
                    "account_id": "",
                    "resource_type": "",
                    "resource_id": "s3-bucket-name",
                },
            ),
            (
                "arn:aws:lambda:us-west-2:123456789012:function:my-function",
                {
                    "partition": "aws",
                    "service": "lambda",
                    "region": "us-west-2",
                    "account_id": "123456789012",
                    "resource_type": "function",
                    "resource_id": "my-function",
                },
            ),
            (
                "arn:aws:states:us-east-1:111122223333:stateMachine:HelloWorld-StateMachine",
                {
                    "partition": "aws",
                    "service": "states",
                    "region": "us-east-1",
                    "account_id": "111122223333",
                    "resource_type": "stateMachine",
                    "resource_id": "HelloWorld-StateMachine",
                },
            ),
            (
                "arn:aws:sqs:region:account_id:queue_name",
                {
                    "partition": "aws",
                    "service": "sqs",
                    "region": "region",
                    "account_id": "account_id",
                    "resource_type": "",
                    "resource_id": "queue_name",
                },
            ),
            (
                "arn:aws:kinesis:us-east-2:123456789012:stream/mystream",
                {
                    "partition": "aws",
                    "service": "kinesis",
                    "region": "us-east-2",
                    "account_id": "123456789012",
                    "resource_type": "stream",
                    "resource_id": "mystream",
                },
            ),
        ]
    )
    def test_valid_arn(self, given_arn, expected_result):
        arn_parts = ARNParts(given_arn)

        self.assertEqual(arn_parts.partition, expected_result["partition"])
        self.assertEqual(arn_parts.service, expected_result["service"])
        self.assertEqual(arn_parts.region, expected_result["region"])
        self.assertEqual(arn_parts.account_id, expected_result["account_id"])
        self.assertEqual(arn_parts.resource_type, expected_result["resource_type"])
        self.assertEqual(arn_parts.resource_id, expected_result["resource_id"])
