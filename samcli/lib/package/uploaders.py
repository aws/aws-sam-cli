"""
Contains Uploaders, a class to hold a S3Uploader and an ECRUploader
"""

from enum import Enum
from typing import Union

from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.s3_uploader import S3Uploader


class Destination(Enum):
    S3 = "s3"  # pylint: disable=invalid-name
    ECR = "ecr"


class Uploaders:
    """
    Class to hold a S3Uploader and an ECRUploader
    """

    _s3_uploader: S3Uploader
    _ecr_uploader: ECRUploader

    def __init__(self, s3_uploader: S3Uploader, ecr_uploader: ECRUploader):
        self._s3_uploader = s3_uploader
        self._ecr_uploader = ecr_uploader

    def get(self, destination: Destination) -> Union[S3Uploader, ECRUploader]:
        if destination == Destination.S3:
            return self._s3_uploader
        if destination == Destination.ECR:
            return self._ecr_uploader
        raise ValueError(f"destination has invalid value: {destination}")

    @property
    def s3(self):
        return self._s3_uploader

    @property
    def ecr(self):
        return self._ecr_uploader
