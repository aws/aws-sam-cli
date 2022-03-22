from unittest import TestCase

from samcli.lib.pipeline.bootstrap.resource import ARNParts, Resource, IAMUser, ECRImageRepository

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

    def test_arn_parts_of_invalid_arn(self):
        with self.assertRaises(ValueError):
            invalid_arn = "invalid_arn"
            ARNParts(arn=invalid_arn)


class TestResource(TestCase):
    def test_resource(self):
        resource = Resource(arn=VALID_ARN, comment="")
        self.assertEqual(resource.arn, VALID_ARN)
        self.assertTrue(resource.is_user_provided)
        self.assertEqual(resource.name(), "resource-id")

        resource = Resource(arn=INVALID_ARN, comment="")
        self.assertEqual(resource.arn, INVALID_ARN)
        self.assertTrue(resource.is_user_provided)
        with self.assertRaises(ValueError):
            resource.name()

        resource = Resource(arn=None, comment="")
        self.assertIsNone(resource.arn)
        self.assertFalse(resource.is_user_provided)
        self.assertIsNone(resource.name())


class TestIAMUser(TestCase):
    def test_create_iam_user(self):
        user: IAMUser = IAMUser(arn=VALID_ARN, comment="user")
        self.assertEqual(user.arn, VALID_ARN)
        self.assertEqual(user.comment, "user")
        self.assertIsNone(user.access_key_id)
        self.assertIsNone(user.secret_access_key)

        user = IAMUser(
            arn=INVALID_ARN,
            access_key_id="any_access_key_id",
            secret_access_key="any_secret_access_key",
            comment="user",
        )
        self.assertEqual(user.arn, INVALID_ARN)
        self.assertEqual(user.comment, "user")
        self.assertEqual(user.access_key_id, "any_access_key_id")
        self.assertEqual(user.secret_access_key, "any_secret_access_key")


class TestECRImageRepository(TestCase):
    def test_get_uri_with_valid_ecr_arn(self):
        valid_ecr_arn = "arn:partition:service:region:account-id:repository/repository-name"
        repo: ECRImageRepository = ECRImageRepository(arn=valid_ecr_arn, comment="ecr")
        self.assertEqual(repo.get_uri(), "account-id.dkr.ecr.region.amazonaws.com/repository-name")
        self.assertEqual("ecr", repo.comment)

    def test_get_uri_with_invalid_ecr_arn(self):
        repo = ECRImageRepository(arn=INVALID_ARN, comment="ecr")
        with self.assertRaises(ValueError):
            repo.get_uri()

    def test_get_uri_with_valid_aws_arn_that_is_invalid_ecr_arn(self):
        ecr_arn_missing_repository_prefix = (
            "arn:partition:service:region:account-id:repository-name-without-repository/-prefix"
        )
        repo = ECRImageRepository(arn=ecr_arn_missing_repository_prefix, comment="ecr")
        with self.assertRaises(ValueError):
            repo.get_uri()
