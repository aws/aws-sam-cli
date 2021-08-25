import unittest
from unittest.mock import MagicMock, patch

from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name


class GetUploadedS3ObjectNameUtils(unittest.TestCase):
    def setUp(self):
        self.file_hash_value = "123456789"
        self.extension = "template"
        self.pre_calculated_hash = "345654323456543"
        self.file_content = MagicMock()
        self.file_path = MagicMock()

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_only_file_content(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(file_content=self.file_content)
        self.assertEqual(res, self.file_hash_value)
        mock_mktempfile.assert_called_once()
        mock_file_checksum.assert_called_once()

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_file_content_and_extension(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(file_content=self.file_content, extension=self.extension)
        self.assertEqual(res, f"{self.file_hash_value}.{self.extension}")
        mock_mktempfile.assert_called_once()
        mock_file_checksum.assert_called_once()

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_only_file_path(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(file_path=self.file_path)
        self.assertEqual(res, self.file_hash_value)
        mock_mktempfile.assert_not_called()
        mock_file_checksum.assert_called_once_with(self.file_path)

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_file_path_and_extension(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(file_path=self.file_path, extension=self.extension)
        self.assertEqual(res, f"{self.file_hash_value}.{self.extension}")
        mock_mktempfile.assert_not_called()
        mock_file_checksum.assert_called_once_with(self.file_path)

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_only_pre_calculated_hash(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(precomputed_md5=self.pre_calculated_hash)
        self.assertEqual(res, self.pre_calculated_hash)
        mock_mktempfile.assert_not_called()
        mock_file_checksum.assert_not_called()

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_pre_calculated_hash_and_extension(
        self, mock_file_checksum, mock_mktempfile
    ):
        mock_file_checksum.return_value = self.file_hash_value
        res = get_uploaded_s3_object_name(precomputed_md5=self.pre_calculated_hash, extension=self.extension)
        self.assertEqual(res, f"{self.pre_calculated_hash}.{self.extension}")
        mock_mktempfile.assert_not_called()
        mock_file_checksum.assert_not_called()

    @patch("samcli.lib.package.local_files_utils.mktempfile")
    @patch("samcli.lib.package.local_files_utils.file_checksum")
    def test_get_uploaded_s3_object_name_with_no_calue(self, mock_file_checksum, mock_mktempfile):
        mock_file_checksum.return_value = self.file_hash_value
        with self.assertRaises(Exception):
            get_uploaded_s3_object_name()
        mock_mktempfile.assert_not_called()
        mock_file_checksum.assert_not_called()
