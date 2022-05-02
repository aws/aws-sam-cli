"""
Utilities involved in Packaging.
"""
import logging
import os
import platform
import re
import shutil
import tempfile
import zipfile
import contextlib
from contextlib import contextmanager
from typing import Dict, Optional, cast

import jmespath

from samcli.commands.package.exceptions import ImageNotFoundError, InvalidLocalPathError
from samcli.lib.package.ecr_utils import is_ecr_url
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.hash import dir_checksum

LOG = logging.getLogger(__name__)

# https://docs.aws.amazon.com/AmazonS3/latest/dev-retired/UsingBucket.html
_REGION_PATTERN = r"[a-zA-Z0-9-]+"
_DOT_AMAZONAWS_COM_PATTERN = r"\.amazonaws\.com(\.cn)?"
_S3_URL_REGEXS = [
    # Path-Style (and ipv6 dualstack)
    # - https://s3.Region.amazonaws.com/bucket-name/key name
    # - https://s3.amazonaws.com/bucket-name/key name (old, without region)
    # - https://s3.dualstack.us-west-2.amazonaws.com/...
    re.compile(rf"http(s)?://s3(.dualstack)?(\.{_REGION_PATTERN})?{_DOT_AMAZONAWS_COM_PATTERN}/.+/.+"),
    # Virtual Hosted-Style (including two legacies)
    # https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html
    # - Virtual Hosted-Style: https://bucket-name.s3.Region.amazonaws.com/key name
    # - Virtual Hosted-Style (Legacy: a dash between S3 and the Region): https://bucket-name.s3-Region.amazonaws.com/...
    # - Virtual Hosted-Style (Legacy Global Endpoint): https://my-bucket.s3.amazonaws.com/...
    re.compile(rf"http(s)?://.+\.s3((.|-){_REGION_PATTERN})?{_DOT_AMAZONAWS_COM_PATTERN}/.+"),
    # S3 access point:
    # - https://AccessPointName-AccountId.s3-accesspoint.region.amazonaws.com
    re.compile(rf"http(s)?://.+-\d+\.s3-accesspoint\.{_REGION_PATTERN}{_DOT_AMAZONAWS_COM_PATTERN}/.+/.+"),
    # S3 protocol URL:
    # - s3://bucket-name/key-name
    re.compile(r"s3://.+/.+"),
]


def is_path_value_valid(path):
    return isinstance(path, str)


def make_abs_path(directory, path):
    if is_path_value_valid(path) and not os.path.isabs(path):
        return os.path.normpath(os.path.join(directory, path))
    return path


def is_s3_protocol_url(url):
    """
    Check whether url is a valid path in the form of "s3://..."
    """
    try:
        S3Uploader.parse_s3_url(url)
        return True
    except ValueError:
        return False


def is_s3_url(url: str) -> bool:
    """
    Check whether a URL is a S3 access URL
    specified at https://docs.aws.amazon.com/AmazonS3/latest/dev-retired/UsingBucket.html
    """
    return any(regex.match(url) for regex in _S3_URL_REGEXS)


def is_local_folder(path):
    return is_path_value_valid(path) and os.path.isdir(path)


def is_local_file(path):
    return is_path_value_valid(path) and os.path.isfile(path)


def is_zip_file(path):
    return is_path_value_valid(path) and zipfile.is_zipfile(path)


def upload_local_image_artifacts(resource_id, resource_dict, property_name, parent_dir, uploader):
    """
    Upload local artifacts referenced by the property at given resource and
    return ECR URL of the uploaded object. It is the responsibility of callers
    to ensure property value is a valid image.

    If path is already a path to S3 object, this method does nothing.

    :param resource_id:     Id of the CloudFormation resource
    :param resource_dict:   Dictionary containing resource definition
    :param property_name:   Property name of CloudFormation resource where this
                            local path is present
    :param parent_dir:      Resolve all relative paths with respect to this
                            directory
    :param uploader:        Method to upload files to ECR

    :return:                ECR URL of the uploaded object
    """

    image_path = jmespath.search(property_name, resource_dict)

    if not image_path:
        message_fmt = "Image not found for {property_name} parameter of {resource_id} resource. \n"
        raise ImageNotFoundError(property_name=property_name, resource_id=resource_id, message_fmt=message_fmt)

    if is_ecr_url(image_path):
        LOG.debug("Property %s of %s is already an ECR URL", property_name, resource_id)
        return image_path

    return uploader.upload(image_path, resource_id)


def upload_local_artifacts(
    resource_id: str,
    resource_dict: Dict,
    property_name: str,
    parent_dir: str,
    uploader: S3Uploader,
    extension: Optional[str] = None,
) -> str:
    """
    Upload local artifacts referenced by the property at given resource and
    return S3 URL of the uploaded object. It is the responsibility of callers
    to ensure property value is a valid string

    If path refers to a file, this method will upload the file. If path refers
    to a folder, this method will zip the folder and upload the zip to S3.
    If path is omitted, this method will zip the current working folder and
    upload.

    If path is already a path to S3 object, this method does nothing.

    :param resource_id:     Id of the CloudFormation resource
    :param resource_dict:   Dictionary containing resource definition
    :param property_name:   Property name of CloudFormation resource where this
                            local path is present
    :param parent_dir:      Resolve all relative paths with respect to this
                            directory
    :param uploader:        Method to upload files to S3
    :param extension:       Extension of the uploaded artifact
    :return:                S3 URL of the uploaded object
    :raise:                 ValueError if path is not a S3 URL or a local path
    """

    local_path = jmespath.search(property_name, resource_dict)

    if local_path is None:
        # Build the root directory and upload to S3
        local_path = parent_dir

    if is_s3_protocol_url(local_path):
        # A valid CloudFormation template will specify artifacts as S3 URLs.
        # This check is supporting the case where your resource does not
        # refer to local artifacts
        # Nothing to do if property value is an S3 URL
        LOG.debug("Property %s of %s is already a S3 URL", property_name, resource_id)
        return cast(str, local_path)

    local_path = make_abs_path(parent_dir, local_path)

    # Or, pointing to a folder. Zip the folder and upload
    if is_local_folder(local_path):
        return zip_and_upload(local_path, uploader, extension)

    # Path could be pointing to a file. Upload the file
    if is_local_file(local_path):
        return uploader.upload_with_dedup(local_path)

    raise InvalidLocalPathError(resource_id=resource_id, property_name=property_name, local_path=local_path)


def resource_not_packageable(resource_dict):
    inline_code = jmespath.search("InlineCode", resource_dict)
    if inline_code is not None:
        return True
    return False


def zip_and_upload(local_path: str, uploader: S3Uploader, extension: Optional[str]) -> str:
    with zip_folder(local_path) as (zip_file, md5_hash):
        return uploader.upload_with_dedup(zip_file, precomputed_md5=md5_hash, extension=extension)


@contextmanager
def zip_folder(folder_path):
    """
    Zip the entire folder and return a file to the zip. Use this inside
    a "with" statement to cleanup the zipfile after it is used.

    Parameters
    ----------
    folder_path : str
        The path of the folder to zip

    Yields
    ------
    zipfile_name : str
        Name of the zipfile
    md5hash : str
        The md5 hash of the directory
    """
    md5hash = dir_checksum(folder_path, followlinks=True)
    filename = os.path.join(tempfile.gettempdir(), "data-" + md5hash)

    zipfile_name = make_zip(filename, folder_path)
    try:
        yield zipfile_name, md5hash
    finally:
        if os.path.exists(zipfile_name):
            os.remove(zipfile_name)


def make_zip(file_name, source_root):
    """
    Create a zip file from the source directory

    Parameters
    ----------
    file_name : str
        The basename of the zip file, without .zip
    source_root : str
        The path to the source directory
    Returns
    -------
    str
        The name of the zip file, including .zip extension
    """
    zipfile_name = "{0}.zip".format(file_name)
    source_root = os.path.abspath(source_root)
    compression_type = zipfile.ZIP_DEFLATED
    with open(zipfile_name, "wb") as f:
        with contextlib.closing(zipfile.ZipFile(f, "w", compression_type)) as zf:
            for root, _, files in os.walk(source_root, followlinks=True):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(full_path, source_root)
                    if platform.system().lower() == "windows":
                        with open(full_path, "rb") as data:
                            file_bytes = data.read()
                            info = zipfile.ZipInfo(relative_path)
                            # Clear external attr set for Windows
                            info.external_attr = 0
                            # Set external attr with Unix 0755 permission
                            # Originally set to 0005 in the discussion below
                            # https://github.com/aws/aws-sam-cli/pull/2193#discussion_r513110608
                            # Changed to 0755 due to a regression in https://github.com/aws/aws-sam-cli/issues/2344
                            # Mimicking Unix permission bits and recommanded permission bits
                            # in the Lambda Trouble Shooting Docs
                            info.external_attr = 0o100755 << 16
                            # Set host OS to Unix
                            info.create_system = 3
                            zf.writestr(info, file_bytes, compress_type=compression_type)
                    else:
                        zf.write(full_path, relative_path)

    return zipfile_name


def copy_to_temp_dir(filepath):
    tmp_dir = tempfile.mkdtemp()
    dst = os.path.join(tmp_dir, os.path.basename(filepath))
    shutil.copyfile(filepath, dst)
    return tmp_dir
