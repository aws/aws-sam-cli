"""Contains utility functions related to AWS S3 service"""
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse


def parse_s3_url(
    url: Any,
    bucket_name_property: str = "Bucket",
    object_key_property: str = "Key",
    version_property: Optional[str] = None,
) -> Dict:
    if isinstance(url, str) and url.startswith("s3://"):
        return _parse_s3_format_url(
            url=url,
            bucket_name_property=bucket_name_property,
            object_key_property=object_key_property,
            version_property=version_property,
        )

    if isinstance(url, str) and url.startswith("https://s3"):
        return _parse_path_style_s3_url(
            url=url, bucket_name_property=bucket_name_property, object_key_property=object_key_property
        )

    raise ValueError("URL given to the parse method is not a valid S3 url {0}".format(url))


def _parse_s3_format_url(
    url: Any,
    bucket_name_property: str = "Bucket",
    object_key_property: str = "Key",
    version_property: Optional[str] = None,
) -> Dict:
    """
    Method for parsing s3 urls that begin with s3://
    e.g. s3://bucket/key
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if parsed.netloc and parsed.path:
        result = dict()
        result[bucket_name_property] = parsed.netloc
        result[object_key_property] = parsed.path.lstrip("/")

        # If there is a query string that has a single versionId field,
        # set the object version and return
        if version_property is not None and "versionId" in query and len(query["versionId"]) == 1:
            result[version_property] = query["versionId"][0]

        return result

    raise ValueError("URL given to the parse method is not a valid S3 url {0}".format(url))


def _parse_path_style_s3_url(
    url: Any,
    bucket_name_property: str = "Bucket",
    object_key_property: str = "Key",
) -> Dict:
    """
    Static method for parsing path style s3 urls.
    e.g. https://s3.us-east-1.amazonaws.com/bucket/key
    """
    parsed = urlparse(url)
    result = dict()
    # parsed.path would point to /bucket/key
    if parsed.path:
        s3_bucket_key = parsed.path.split("/", 2)[1:]

        result[bucket_name_property] = s3_bucket_key[0]
        result[object_key_property] = s3_bucket_key[1]

        return result
    raise ValueError("URL given to the parse method is not a valid S3 url {0}".format(url))
