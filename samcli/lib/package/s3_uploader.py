"""
Client for uploading packaged artifacts to s3
"""

# Copyright 2012-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import logging
import os
import sys
import threading
from collections import abc
from typing import Any, Optional, cast

import botocore
import botocore.exceptions
from boto3.s3 import transfer
from boto3.s3.transfer import ProgressCallbackInvoker

from samcli.commands.package.exceptions import BucketNotSpecifiedError, NoSuchBucketError
from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name
from samcli.lib.utils.s3 import parse_s3_url

LOG = logging.getLogger(__name__)


class S3Uploader:
    """
    Class to upload objects to S3 bucket that use versioning. If bucket
    does not already use versioning, this class will turn on versioning.
    """

    @property
    def artifact_metadata(self):
        """
        Metadata to attach to the object(s) uploaded by the uploader.
        """
        return self._artifact_metadata

    @artifact_metadata.setter
    def artifact_metadata(self, val):
        if val is not None and not isinstance(val, abc.Mapping):
            raise TypeError("Artifact metadata should be in dict type")
        self._artifact_metadata = val

    def __init__(
        self,
        s3_client: Any,
        bucket_name: str,
        prefix: Optional[str] = None,
        kms_key_id: Optional[str] = None,
        force_upload: bool = False,
        no_progressbar: bool = False,
    ):
        self.s3 = s3_client
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.kms_key_id = kms_key_id or None
        self.force_upload = force_upload
        self.no_progressbar = no_progressbar
        self.transfer_manager = transfer.create_transfer_manager(self.s3, transfer.TransferConfig())

        self._artifact_metadata = None

    def upload(self, file_name: str, remote_path: str) -> str:
        """
        Uploads given file to S3
        :param file_name: Path to the file that will be uploaded
        :param remote_path:  be uploaded
        :return: VersionId of the latest upload
        """

        if self.prefix:
            remote_path = "{0}/{1}".format(self.prefix, remote_path)

        # Check if a file with same data exists
        if not self.force_upload and self.file_exists(remote_path):
            LOG.info("File with same data already exists at %s, skipping upload", remote_path)
            return self.make_url(remote_path)

        try:
            # Default to regular server-side encryption unless customer has
            # specified their own KMS keys
            additional_args = {"ServerSideEncryption": "AES256"}

            if self.kms_key_id:
                additional_args["ServerSideEncryption"] = "aws:kms"
                additional_args["SSEKMSKeyId"] = self.kms_key_id

            if self.artifact_metadata:
                additional_args["Metadata"] = self.artifact_metadata

            if not self.bucket_name:
                raise BucketNotSpecifiedError()

            if not self.no_progressbar:
                print_progress_callback = ProgressCallbackInvoker(
                    ProgressPercentage(file_name, remote_path).on_progress
                )
                future = self.transfer_manager.upload(
                    file_name, self.bucket_name, remote_path, additional_args, [print_progress_callback]
                )
            else:
                future = self.transfer_manager.upload(file_name, self.bucket_name, remote_path, additional_args)
            future.result()

            return self.make_url(remote_path)

        except botocore.exceptions.ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            if error_code == "NoSuchBucket":
                raise NoSuchBucketError(bucket_name=self.bucket_name) from ex
            raise ex

    def upload_with_dedup(
        self, file_name: str, extension: Optional[str] = None, precomputed_md5: Optional[str] = None
    ) -> str:
        """
        Makes and returns name of the S3 object based on the file's MD5 sum

        :param file_name: file to upload
        :param extension: String of file extension to append to the object
        :param precomputed_md5: Specified md5 hash for the file to be uploaded.
        :return: S3 URL of the uploaded object
        """

        # This construction of remote_path is critical to preventing duplicate
        # uploads of same object. Uploader will check if the file exists in S3
        # and re-upload only if necessary. So the template points to same file
        # in multiple places, this will upload only once
        remote_path = get_uploaded_s3_object_name(
            precomputed_md5=precomputed_md5, file_path=file_name, extension=extension
        )
        return self.upload(file_name, remote_path)

    def delete_artifact(self, remote_path: str, is_key: bool = False) -> bool:
        """
        Deletes a given file from S3
        :param remote_path: Path to the file that will be deleted
        :param is_key: If the given remote_path is the key or a file_name

        :return: metadata dict of the deleted object
        """
        try:
            if not self.bucket_name:
                LOG.error("Bucket not specified")
                raise BucketNotSpecifiedError()

            key = remote_path
            if self.prefix and not is_key:
                key = "{0}/{1}".format(self.prefix, remote_path)

            # Deleting Specific file with key
            if self.file_exists(remote_path=key):
                LOG.info("\t- Deleting S3 object with key %s", key)
                self.s3.delete_object(Bucket=self.bucket_name, Key=key)
                LOG.debug("Deleted s3 object with key %s successfully", key)
                return True

            # Given s3 object key does not exist
            LOG.debug("Could not find the S3 file with the key %s", key)
            LOG.info("\t- Could not find and delete the S3 object with the key %s", key)
            return False

        except botocore.exceptions.ClientError as ex:
            error_code = ex.response["Error"]["Code"]
            if error_code == "NoSuchBucket":
                LOG.error("Provided bucket %s does not exist ", self.bucket_name)
                raise NoSuchBucketError(bucket_name=self.bucket_name) from ex
            raise ex

    def delete_prefix_artifacts(self):
        """
        Deletes all the files from the prefix in S3
        """
        if not self.bucket_name:
            LOG.error("Bucket not specified")
            raise BucketNotSpecifiedError()
        if self.prefix:
            # Note: list_objects_v2 api uses prefix to fetch the keys that begin with the prefix
            # To restrict fetching files with exact prefix self.prefix, "/" is used below.
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=self.prefix + "/")
            prefix_files = response.get("Contents", [])
            for obj in prefix_files:
                self.delete_artifact(obj["Key"], True)

    def file_exists(self, remote_path: str) -> bool:
        """
        Check if the file we are trying to upload already exists in S3

        :param remote_path:
        :return: True, if file exists. False, otherwise
        """

        try:
            # Find the object that matches this ETag
            if not self.bucket_name:
                raise BucketNotSpecifiedError()
            self.s3.head_object(Bucket=self.bucket_name, Key=remote_path)
            return True
        except botocore.exceptions.ClientError:
            # Either File does not exist or we are unable to get
            # this information.
            return False

    def make_url(self, obj_path: str) -> str:
        if not self.bucket_name:
            raise BucketNotSpecifiedError()
        return "s3://{0}/{1}".format(self.bucket_name, obj_path)

    def to_path_style_s3_url(self, key: str, version: Optional[str] = None) -> str:
        """
        This link describes the format of Path Style URLs
        http://docs.aws.amazon.com/AmazonS3/latest/dev/UsingBucket.html#access-bucket-intro
        """
        base = self.s3.meta.endpoint_url
        result = "{0}/{1}/{2}".format(base, self.bucket_name, key)
        if version:
            result = "{0}?versionId={1}".format(result, version)

        return result

    def get_version_of_artifact(self, s3_url: str) -> str:
        """
        Returns version information of the S3 object that is given as S3 URL
        """
        parsed_s3_url = parse_s3_url(s3_url)
        s3_bucket = parsed_s3_url["Bucket"]
        s3_key = parsed_s3_url["Key"]
        s3_object_tagging = self.s3.get_object_tagging(Bucket=s3_bucket, Key=s3_key)
        LOG.debug("S3 Object (%s) tagging information %s", s3_url, s3_object_tagging)
        s3_object_version_id = s3_object_tagging["VersionId"]
        return cast(str, s3_object_version_id)


class ProgressPercentage:
    # This class was copied directly from S3Transfer docs

    def __init__(self, filename, remote_path):
        self._filename = filename
        self._remote_path = remote_path
        self._size = os.path.getsize(filename)
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def on_progress(self, bytes_transferred, **kwargs):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        with self._lock:
            self._seen_so_far += bytes_transferred
            percentage = (self._seen_so_far / self._size) * 100  # noqa: PLR2004
            sys.stderr.write(
                "\r\tUploading to %s  %s / %s  (%.2f%%)"
                % (self._remote_path, self._seen_so_far, self._size, percentage)
            )
            sys.stderr.flush()
            if int(percentage) == 100:  # noqa: PLR2004
                sys.stderr.write("\n")
