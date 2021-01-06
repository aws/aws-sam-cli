from unittest import TestCase
from unittest.mock import MagicMock
from parameterized import parameterized, param

from samcli.lib.package.code_signer import CodeSigner, CodeSigningJobFailureException, CodeSigningInitiationException


class TestCodeSigner(TestCase):
    def setUp(self):
        self.signer_client = MagicMock()

    @parameterized.expand(
        [
            param({}),
            param({"MyFunction": {"profile_name": "profile1", "profile_owner": ""}}),
        ]
    )
    def test_should_sign_package(self, signing_profiles):
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        should_sign_package = code_signer.should_sign_package("MyFunction")
        if len(signing_profiles) > 0:
            self.assertEqual(should_sign_package, True)
        else:
            self.assertEqual(should_sign_package, False)

    @parameterized.expand(["", "MyProfileOwner"])
    def test_sign_package_successfully(self, given_profile_owner):
        # prepare code signing config
        resource_id = "MyFunction"
        given_profile_name = "MyProfile"
        signing_profiles = {resource_id: {"profile_name": given_profile_name, "profile_owner": given_profile_owner}}
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        # prepare object details that is going to be signed
        given_s3_bucket = "bucket"
        given_s3_key = "path/to/unsigned/package"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_key}"
        given_s3_object_version = "objectVersion"
        given_signed_object_location = "path/to/signed/object"
        given_job_id = "signingJobId"

        # prepare method mocks
        mocked_waiter = MagicMock()
        self.signer_client.start_signing_job.return_value = {"jobId": given_job_id}
        self.signer_client.get_waiter.return_value = mocked_waiter
        self.signer_client.describe_signing_job.return_value = {
            "status": "Succeeded",
            "signedObject": {"s3": {"key": given_signed_object_location}},
        }

        # make the actual call
        signed_object_location = code_signer.sign_package(resource_id, given_s3_url, given_s3_object_version)

        # start verifying calls and responses
        expected_start_signing_job_params_source = {
            "s3": {"bucketName": given_s3_bucket, "key": given_s3_key, "version": given_s3_object_version}
        }
        expected_start_signing_job_params_destination = {
            "s3": {"bucketName": given_s3_bucket, "prefix": "path/to/unsigned/signed_"}
        }

        if given_profile_owner:
            self.signer_client.start_signing_job.assert_called_with(
                source=expected_start_signing_job_params_source,
                destination=expected_start_signing_job_params_destination,
                profileName=given_profile_name,
                profileOwner=given_profile_owner,
            )
        else:
            self.signer_client.start_signing_job.assert_called_with(
                source=expected_start_signing_job_params_source,
                destination=expected_start_signing_job_params_destination,
                profileName=given_profile_name,
            )

        self.signer_client.get_waiter.assert_called_with("successful_signing_job")
        mocked_waiter.wait.assert_called_with(jobId=given_job_id, WaiterConfig={"Delay": 5})

        self.signer_client.describe_signing_job.assert_called_with(jobId=given_job_id)
        self.assertEqual(signed_object_location, f"s3://{given_s3_bucket}/{given_signed_object_location}")

    def test_sign_package_should_fail_if_status_not_succeed(self):
        # prepare code signing config
        resource_id = "MyFunction"
        given_profile_name = "MyProfile"
        signing_profiles = {resource_id: {"profile_name": given_profile_name, "profile_owner": ""}}
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        # prepare object details that is going to be signed
        given_s3_bucket = "bucket"
        given_s3_key = "path/to/unsigned/package"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_key}"
        given_s3_object_version = "objectVersion"
        given_signed_object_location = "path/to/signed/object"
        given_job_id = "signingJobId"

        # prepare method mocks
        mocked_waiter = MagicMock()
        self.signer_client.start_signing_job.return_value = {"jobId": given_job_id}
        self.signer_client.get_waiter.return_value = mocked_waiter
        self.signer_client.describe_signing_job.return_value = {
            "status": "Fail",
            "signedObject": {"s3": {"key": given_signed_object_location}},
        }

        # make the actual call
        with self.assertRaises(CodeSigningJobFailureException):
            code_signer.sign_package(resource_id, given_s3_url, given_s3_object_version)

    def test_sign_package_should_fail_if_initiate_signing_fails(self):
        # prepare code signing config
        resource_id = "MyFunction"
        given_profile_name = "MyProfile"
        signing_profiles = {resource_id: {"profile_name": given_profile_name, "profile_owner": ""}}
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        # prepare object details that is going to be signed
        given_s3_bucket = "bucket"
        given_s3_key = "path/to/unsigned/package"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_key}"
        given_s3_object_version = "objectVersion"

        # mock exception when initiating signing job
        self.signer_client.start_signing_job.side_effect = Exception()

        with self.assertRaises(CodeSigningInitiationException):
            code_signer.sign_package(resource_id, given_s3_url, given_s3_object_version)

    def test_sign_package_should_fail_if_waiter_fails(self):
        # prepare code signing config
        resource_id = "MyFunction"
        given_profile_name = "MyProfile"
        signing_profiles = {resource_id: {"profile_name": given_profile_name, "profile_owner": ""}}
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        # prepare object details that is going to be signed
        given_s3_bucket = "bucket"
        given_s3_key = "path/to/unsigned/package"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_key}"
        given_s3_object_version = "objectVersion"
        given_job_id = "signingJobId"

        # prepare method mocks
        self.signer_client.start_signing_job.return_value = {"jobId": given_job_id}
        self.signer_client.get_waiter.side_effect = Exception()

        # make the actual call
        with self.assertRaises(CodeSigningJobFailureException):
            code_signer.sign_package(resource_id, given_s3_url, given_s3_object_version)

    def test_sign_package_should_fail_if_describe_job_fails(self):
        # prepare code signing config
        resource_id = "MyFunction"
        given_profile_name = "MyProfile"
        signing_profiles = {resource_id: {"profile_name": given_profile_name, "profile_owner": ""}}
        code_signer = CodeSigner(self.signer_client, signing_profiles)

        # prepare object details that is going to be signed
        given_s3_bucket = "bucket"
        given_s3_key = "path/to/unsigned/package"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_key}"
        given_s3_object_version = "objectVersion"
        given_job_id = "signingJobId"

        # prepare method mocks
        mocked_waiter = MagicMock()
        self.signer_client.start_signing_job.return_value = {"jobId": given_job_id}
        self.signer_client.get_waiter.return_value = mocked_waiter
        self.signer_client.describe_signing_job.side_effect = Exception()

        # make the actual call
        with self.assertRaises(CodeSigningJobFailureException):
            code_signer.sign_package(resource_id, given_s3_url, given_s3_object_version)
