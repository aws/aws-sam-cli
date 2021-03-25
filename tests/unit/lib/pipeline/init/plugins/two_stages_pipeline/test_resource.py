from unittest import TestCase
from samcli.lib.pipeline.init.plugins.two_stages_pipeline.resource import Resource, Deployer, S3Bucket  # type: ignore

VALID_AWS_ARN = "arn:partition:service:region:account-id:resource-id"
INVALID_AWS_ARN = "ARN"


class TestResource(TestCase):
    def test_resource(self):
        resource = Resource(arn=VALID_AWS_ARN)
        self.assertEqual(resource.arn, VALID_AWS_ARN)
        self.assertTrue(resource.is_user_provided)
        self.assertEqual(resource.name(), "resource-id")

        resource = Resource(arn=INVALID_AWS_ARN)
        self.assertEqual(resource.arn, INVALID_AWS_ARN)
        self.assertTrue(resource.is_user_provided)
        self.assertEqual(resource.name(), "ARN")

        resource = Resource(arn=None)
        self.assertIsNone(resource.arn)
        self.assertFalse(resource.is_user_provided)
        self.assertIsNone(resource.name())


class TestDeployerResource(TestCase):
    def test_deployer_resource(self):
        deployer = Deployer(arn=VALID_AWS_ARN)
        self.assertEqual(deployer.arn, VALID_AWS_ARN)
        self.assertTrue(deployer.is_user_provided)
        self.assertEqual(deployer.name(), "resource-id")
        self.assertIsNone(deployer.access_key_id)
        self.assertIsNone(deployer.secret_access_key)

        deployer = Deployer(arn=VALID_AWS_ARN, access_key_id="access_key_id", secret_access_key="secret_access_key")
        self.assertEqual("access_key_id", deployer.access_key_id)
        self.assertEqual("secret_access_key", deployer.secret_access_key)


class TestS3BucketResource(TestCase):
    def test_s3bucket_resource(self):
        bucket = S3Bucket(arn=VALID_AWS_ARN)
        self.assertEqual(bucket.arn, VALID_AWS_ARN)
        self.assertTrue(bucket.is_user_provided)
        self.assertEqual(bucket.name(), "resource-id")
        self.assertIsNone(bucket.kms_key_arn)

        bucket = S3Bucket(arn=VALID_AWS_ARN, kms_key_arn="kms_key_arn")
        self.assertEqual("kms_key_arn", bucket.kms_key_arn)
