import os

from unittest import TestCase
from unittest.mock import MagicMock
import tempfile

from pathlib import Path
from botocore.exceptions import ClientError

from samcli.commands.package.exceptions import NoSuchBucketError, BucketNotSpecifiedError
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.hash import file_checksum


class TestS3Uploader(TestCase):
    def setUp(self):
        self.s3 = MagicMock()
        self.bucket_name = "mock-bucket"
        self.prefix = "mock-prefix"
        self.kms_key_id = "mock-kms-key-id"
        self.force_upload = False
        self.no_progressbar = False

    def test_s3_uploader_init(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        self.assertEqual(s3_uploader.s3, self.s3)
        self.assertEqual(s3_uploader.bucket_name, self.bucket_name)
        self.assertEqual(s3_uploader.prefix, self.prefix)
        self.assertEqual(s3_uploader.kms_key_id, self.kms_key_id)
        self.assertEqual(s3_uploader.force_upload, self.force_upload)
        self.assertEqual(s3_uploader.no_progressbar, self.no_progressbar)
        self.assertEqual(s3_uploader.artifact_metadata, None)

    def test_s3_uploader_artifact_metadata(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        s3_uploader.artifact_metadata = {}
        self.assertEqual(s3_uploader.artifact_metadata, {})
        with self.assertRaises(TypeError):
            s3_uploader.artifact_metadata = "Not a dict"

    def test_s3_upload_skip_upload(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=None,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        with tempfile.NamedTemporaryFile() as f:
            s3_url = s3_uploader.upload("package.zip", f.name)
            self.assertEqual(s3_url, "s3://{0}/{1}".format(self.bucket_name, f.name))

    def test_s3_upload_skip_upload_with_prefix(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        with tempfile.NamedTemporaryFile() as f:
            s3_url = s3_uploader.upload("package.zip", f.name)
            self.assertEqual(s3_url, "s3://{0}/{1}/{2}".format(self.bucket_name, self.prefix, f.name))

    def test_s3_upload_bucket_not_found(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=True,
            no_progressbar=self.no_progressbar,
        )
        remote_path = Path.joinpath(Path(os.getcwd()), Path("tmp"))
        s3_uploader.transfer_manager.upload = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Code": "NoSuchBucket"}}, operation_name="create_object")
        )
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(NoSuchBucketError):
                s3_uploader.upload(f.name, remote_path)

    def test_s3_upload_general_error(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=True,
            no_progressbar=self.no_progressbar,
        )
        remote_path = Path.joinpath(Path(os.getcwd()), Path("tmp"))
        s3_uploader.transfer_manager.upload = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Code": "Unknown"}}, operation_name="create_object")
        )
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(ClientError):
                s3_uploader.upload(f.name, remote_path)

    def test_file_checksum(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f:
            f.write(b"Hello World!")
            f.seek(0)
            self.assertEqual("ed076287532e86365e841e92bfc50d8c", file_checksum(f.name))

    def test_path_style_s3_url(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        self.s3.meta.endpoint_url = "s3_url"
        self.assertEqual(
            s3_uploader.to_path_style_s3_url("package.zip", version="1"), "s3_url/mock-bucket/package.zip?versionId=1"
        )

    def test_s3_upload(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        s3_uploader.artifact_metadata = {"a": "b"}
        remote_path = Path.joinpath(Path(os.getcwd()), Path("tmp"))
        self.s3.head_object = MagicMock(side_effect=ClientError(error_response={}, operation_name="head_object"))
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            s3_url = s3_uploader.upload(f.name, remote_path)
            self.assertEqual(s3_url, "s3://{0}/{1}/{2}".format(self.bucket_name, self.prefix, remote_path))

    def test_s3_upload_no_bucket(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=None,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        s3_uploader.artifact_metadata = {"a": "b"}
        remote_path = Path.joinpath(Path(os.getcwd()), Path("tmp"))
        with self.assertRaises(BucketNotSpecifiedError) as ex:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                s3_uploader.upload(f.name, remote_path)
            self.assertEqual(BucketNotSpecifiedError().message, str(ex))

    def test_s3_delete_artifact(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=None,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        s3_uploader.artifact_metadata = {"a": "b"}
        with self.assertRaises(BucketNotSpecifiedError) as ex:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                self.assertEqual(s3_uploader.delete_artifact(f.name), {"a": "b"})

    def test_s3_delete_artifact_no_bucket(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=None,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        with self.assertRaises(BucketNotSpecifiedError) as ex:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                s3_uploader.delete_artifact(f.name)
            self.assertEqual(BucketNotSpecifiedError().message, str(ex))

    def test_s3_delete_artifact_bucket_not_found(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=True,
            no_progressbar=self.no_progressbar,
        )

        s3_uploader.s3.delete_object = MagicMock(
            side_effect=ClientError(error_response={"Error": {"Code": "NoSuchBucket"}}, operation_name="create_object")
        )
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(NoSuchBucketError):
                s3_uploader.delete_artifact(f.name)

    def test_s3_upload_with_dedup(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
            no_progressbar=self.no_progressbar,
        )
        self.s3.head_object = MagicMock(side_effect=ClientError(error_response={}, operation_name="head_object"))
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            s3_url = s3_uploader.upload_with_dedup(f.name, "zip")
            self.assertEqual(
                s3_url, "s3://{0}/{1}/{2}.zip".format(self.bucket_name, self.prefix, file_checksum(f.name))
            )

    def test_get_version_of_artifact(self):
        s3_uploader = S3Uploader(
            s3_client=self.s3,
            bucket_name=self.bucket_name,
            prefix=self.prefix,
            kms_key_id=self.kms_key_id,
            force_upload=self.force_upload,
        )

        given_version_id = "versionId"
        given_s3_bucket = "mybucket"
        given_s3_location = "my/object/location"
        given_s3_url = f"s3://{given_s3_bucket}/{given_s3_location}"

        self.s3.get_object_tagging.return_value = {"VersionId": given_version_id}

        version_id = s3_uploader.get_version_of_artifact(given_s3_url)

        self.s3.get_object_tagging.assert_called_with(Bucket=given_s3_bucket, Key=given_s3_location)
        self.assertEqual(version_id, given_version_id)
