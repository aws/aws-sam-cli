import tempfile
from unittest import TestCase

from parameterized import parameterized

from samcli.lib.package import utils
from samcli.lib.package.utils import zip_folder, make_zip


class TestPackageUtils(TestCase):
    @parameterized.expand(
        [
            # path like
            "https://s3.us-west-2.amazonaws.com/bucket-name/some/path/object.html",
            "http://s3.amazonaws.com/bucket-name/some/path/object.html",
            "https://s3.dualstack.us-west-2.amazonaws.com/bucket-name/some/path/object.html",
            "https://s3.dualstack.us-west-2.amazonaws.com.cn/bucket-name/some/path/object.html",
            # virual host
            "http://bucket-name.s3.us-west-2.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3-us-west-2.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3.amazonaws.com.cn/some/path/object.html",
            # access point
            "https://access-name-123456.s3-accesspoint.us-west-2.amazonaws.com/some/path/object.html",
            "http://access-name-899889.s3-accesspoint.us-east-1.amazonaws.com/some/path/object.html",
            "http://access-name-899889.s3-accesspoint.us-east-1.amazonaws.com.cn/some/path/object.html",
            # s3://
            "s3://bucket-name/path/to/object",
        ]
    )
    def test_is_s3_url(self, url):
        self.assertTrue(utils.is_s3_url(url))

    @parameterized.expand(
        [
            # path like
            "https://s3.$region.amazonaws.com.abc/bucket-name/some/path/object.html",  # invalid domain
            "https://s3.$region.amazonaws.com/bucket-name/some/path/object.html",  # invalid region
            "https://s3.amazonaws.com/object.html",  # no bucket
            # virual host
            "https://bucket-name.s3-us-west-2.amazonaws.com/",  # no object
            # access point
            "https://access-name.s3-accesspoint.us-west-2.amazonaws.com/some/path/object.html",  # no account id
            # s3://
            "s3://bucket-name",  # no object
            "s3:://bucket-name",  # typo
        ]
    )
    def test_is_not_s3_url(self, url):
        self.assertFalse(utils.is_s3_url(url))

    def test_zip_folder_uses_different_path_for_same_file_in_different_run(self):
        all_zip_files = set()
        previous_md5_hash = None
        for i in range(5):
            tmp_folder = tempfile.mkdtemp()
            with zip_folder(tmp_folder, make_zip) as (zip_file, md5_hash):
                self.assertNotIn(zip_file, all_zip_files, "Each zip file should be unique!")
                all_zip_files.add(zip_file)
                if not previous_md5_hash:
                    previous_md5_hash = md5_hash
                else:
                    self.assertEqual(previous_md5_hash, md5_hash)
