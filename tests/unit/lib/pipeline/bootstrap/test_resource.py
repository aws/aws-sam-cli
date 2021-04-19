from unittest import TestCase
from unittest.mock import Mock, patch, call

from samcli.lib.pipeline.bootstrap.resource import ARNParts, Resource, S3Bucket, IamUser, EcrRepo

VALID_ARN = "arn:partition:service:region:account-id:resource-id"
INVALID_ARN = "ARN"


class TestArnParts(TestCase):
    def test_arn_parts_of_valid_arn(self):
        arn_parts: ARNParts = ARNParts(arn=VALID_ARN)
        self.assertEqual(arn_parts.partition, "partition")
        self.assertEqual(arn_parts.service, "service")
        self.assertEqual(arn_parts.region, "region")
        self.assertEqual(arn_parts.account_id, "account-id")
        self.assertEqual(arn_parts.resource_id, "resource-id")

    def test_arn_parts_of_none_arn_is_invalid(self):
        with self.assertRaises(ValueError):
            ARNParts(arn=None)

    def test_arn_parts_of_none_string_arn_is_invalid(self):
        with self.assertRaises(ValueError):
            any_non_string = 1
            ARNParts(arn=any_non_string)

    def test_arn_parts_of_invalid_arn(self):
        with self.assertRaises(ValueError):
            invalid_arn = "invalid_arn"
            ARNParts(arn=invalid_arn)


class TestResource(TestCase):
    def test_resource(self):
        resource = Resource(arn=VALID_ARN)
        self.assertEqual(resource.arn, VALID_ARN)
        self.assertTrue(resource.is_user_provided)
        self.assertEqual(resource.name(), "resource-id")

        resource = Resource(arn=INVALID_ARN)
        self.assertEqual(resource.arn, INVALID_ARN)
        self.assertTrue(resource.is_user_provided)
        with self.assertRaises(ValueError):
            resource.name()

        resource = Resource(arn=None)
        self.assertIsNone(resource.arn)
        self.assertFalse(resource.is_user_provided)
        self.assertIsNone(resource.name())


class TestIamUser(TestCase):
    def test_create_iam_user(self):
        user: IamUser = IamUser(arn=VALID_ARN)
        self.assertEquals(user.arn, VALID_ARN)
        self.assertIsNone(user.access_key_id)
        self.assertIsNone(user.secret_access_key)

        user = IamUser(arn=INVALID_ARN, access_key_id="any_access_key_id", secret_access_key="any_secret_access_key")
        self.assertEquals(user.arn, INVALID_ARN)
        self.assertEquals(user.access_key_id, "any_access_key_id")
        self.assertEquals(user.secret_access_key, "any_secret_access_key")


class TestS3Bucket(TestCase):
    def test_create_s3_bucket(self):
        bucket: S3Bucket = S3Bucket(arn=VALID_ARN)
        self.assertEquals(bucket.arn, VALID_ARN)
        self.assertIsNone(bucket.kms_key_arn)

        bucket = S3Bucket(arn=INVALID_ARN, kms_key_arn="any_kms_key_arn")
        self.assertEquals(bucket.arn, INVALID_ARN)
        self.assertEquals(bucket.kms_key_arn, "any_kms_key_arn")


class TestEcrRepo(TestCase):
    def test_get_uri(self):
        valid_ecr_arn = "arn:partition:service:region:account-id:repository/repository-name"
        repo: EcrRepo = EcrRepo(arn=valid_ecr_arn)
        self.assertEqual(repo.get_uri(), "account-id.dkr.ecr.region.amazonaws.com/repository-name")

        valid_ecr_arn = "arn:partition:service:region:account-id:repository/repository-name"
        repo = EcrRepo(arn=INVALID_ARN)
        with self.assertRaises(ValueError):
            repo.get_uri()

        ecr_arn_missing_repository_prefix = "arn:partition:service:region:account-id:repository-name-not-prefixed-with-repository/"
        repo = EcrRepo(arn=ecr_arn_missing_repository_prefix)
        with self.assertRaises(ValueError):
            repo.get_uri()
