"""
Contains Uploaders, a class to hold a S3Uploader and an ECRUploader
"""

from enum import Enum
from typing import Optional, Union

from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.s3_uploader import S3Uploader


class Destination(Enum):
    S3 = "s3"  # pylint: disable=invalid-name
    ECR = "ecr"
    # Web Function code, which can use a different bucket
    WEB_FUNCTION_S3 = "web_function_s3"


class Uploaders:
    """
    Class to hold a S3Uploader and an ECRUploader
    """

    _s3_uploader: S3Uploader
    _ecr_uploader: ECRUploader
    _web_function_s3_uploader: Optional[S3Uploader]
    # Export holding web_function_s3_uploader's bucket name
    web_function_bucket_export: Optional[str]

    def __init__(
        self,
        s3_uploader: S3Uploader,
        ecr_uploader: ECRUploader,
        web_function_s3_uploader: Optional[S3Uploader] = None,
        web_function_bucket_export: Optional[str] = None,
    ):
        self._s3_uploader = s3_uploader
        self._ecr_uploader = ecr_uploader
        self._web_function_s3_uploader = web_function_s3_uploader
        self.web_function_bucket_export = web_function_bucket_export

    def get(self, destination: Destination) -> Union[S3Uploader, ECRUploader]:
        if destination == Destination.S3:
            return self._s3_uploader
        if destination == Destination.ECR:
            return self._ecr_uploader
        if destination == Destination.WEB_FUNCTION_S3:
            return self._web_function_s3_uploader or self._s3_uploader
        raise ValueError(f"destination has invalid value: {destination}")

    @property
    def s3(self):
        return self._s3_uploader

    @property
    def ecr(self):
        return self._ecr_uploader
