from unittest import TestCase
from samcli.lib.utils.s3 import parse_s3_url


class TestS3Utils(TestCase):
    def test_parse_s3_url(self):
        valid = [
            {"url": "s3://foo/bar", "result": {"Bucket": "foo", "Key": "bar"}},
            {"url": "s3://foo/bar/cat/dog", "result": {"Bucket": "foo", "Key": "bar/cat/dog"}},
            {
                "url": "s3://foo/bar/baz?versionId=abc&param1=val1&param2=val2",
                "result": {"Bucket": "foo", "Key": "bar/baz", "VersionId": "abc"},
            },
            {
                # VersionId is not returned if there are more than one versionId
                # keys in query parameter
                "url": "s3://foo/bar/baz?versionId=abc&versionId=123",
                "result": {"Bucket": "foo", "Key": "bar/baz"},
            },
            {
                # Path style url
                "url": "https://s3-eu-west-1.amazonaws.com/bucket/key",
                "result": {"Bucket": "bucket", "Key": "key"},
            },
            {
                # Path style url
                "url": "https://s3.us-east-1.amazonaws.com/bucket/key",
                "result": {"Bucket": "bucket", "Key": "key"},
            },
        ]

        invalid = [
            # For purposes of exporter, we need S3 URLs to point to an object
            # and not a bucket
            "s3://foo",
            "https://www.amazon.com",
            "https://s3.us-east-1.amazonaws.com",
        ]

        for config in valid:
            result = parse_s3_url(
                config["url"], bucket_name_property="Bucket", object_key_property="Key", version_property="VersionId"
            )

            self.assertEqual(result, config["result"])

        for url in invalid:
            with self.assertRaises(ValueError):
                parse_s3_url(url)
