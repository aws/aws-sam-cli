import io
from unittest import TestCase
import tarfile
from unittest.mock import Mock, patch, call

from samcli.lib.utils.tar import extract_tarfile, create_tarball, _is_within_directory


class TestTar(TestCase):
    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar.TemporaryFile")
    def test_generating_tarball(self, temporary_file_patch, tarfile_open_patch):
        temp_file_mock = Mock()
        temporary_file_patch.return_value = temp_file_mock

        tarfile_file_mock = Mock()
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        with create_tarball({"/some/path": "/layer1", "/some/dockerfile/path": "/Dockerfile"}) as acutal:
            self.assertEqual(acutal, temp_file_mock)

        tarfile_file_mock.add.assert_called()
        tarfile_file_mock.add.assert_has_calls(
            [
                call("/some/path", arcname="/layer1", filter=None),
                call("/some/dockerfile/path", arcname="/Dockerfile", filter=None),
            ],
            any_order=True,
        )

        temp_file_mock.flush.assert_called_once()
        temp_file_mock.seek.assert_called_once_with(0)
        temp_file_mock.close.assert_called_once()
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w")

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar.TemporaryFile")
    def test_generating_tarball_with_gzip(self, temporary_file_patch, tarfile_open_patch):
        temp_file_mock = Mock()
        temporary_file_patch.return_value = temp_file_mock

        tarfile_file_mock = Mock()
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        with create_tarball({"/some/path": "/layer1", "/some/dockerfile/path": "/Dockerfile"}, mode="w:gz") as acutal:
            self.assertEqual(acutal, temp_file_mock)

        tarfile_file_mock.add.assert_called()
        tarfile_file_mock.add.assert_has_calls(
            [
                call("/some/path", arcname="/layer1", filter=None),
                call("/some/dockerfile/path", arcname="/Dockerfile", filter=None),
            ],
            any_order=True,
        )

        temp_file_mock.flush.assert_called_once()
        temp_file_mock.seek.assert_called_once_with(0)
        temp_file_mock.close.assert_called_once()
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w:gz")

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar.TemporaryFile")
    def test_generating_tarball_with_filter(self, temporary_file_patch, tarfile_open_patch):
        temp_file_mock = Mock()
        temporary_file_patch.return_value = temp_file_mock

        tarfile_file_mock = Mock()
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        def tar_filter(tar_info):
            tar_info.mode = 0o500
            return tar_info

        with create_tarball(
            {"/some/path": "/layer1", "/some/dockerfile/path": "/Dockerfile"}, tar_filter=tar_filter
        ) as acutal:
            self.assertEqual(acutal, temp_file_mock)

        tarfile_file_mock.add.assert_called()
        tarfile_file_mock.add.assert_has_calls(
            [
                call("/some/path", arcname="/layer1", filter=tar_filter),
                call("/some/dockerfile/path", arcname="/Dockerfile", filter=tar_filter),
            ],
            any_order=True,
        )

        temp_file_mock.flush.assert_called_once()
        temp_file_mock.seek.assert_called_once_with(0)
        temp_file_mock.close.assert_called_once()
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w")

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_file_name(self, is_within_directory_patch, tarfile_open_patch):
        tarfile_path = "/test_tarfile_path/"
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = True

        tarfile_file_mock = Mock()
        tar_file_obj_mock = Mock()
        tar_file_obj_mock.name = "obj_name"
        tarfile_file_mock.getmembers.return_value = [tar_file_obj_mock]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(tarfile_path=tarfile_path, unpack_dir=unpack_dir)

        is_within_directory_patch.assert_called_once()
        tarfile_file_mock.getmembers.assert_called_once()
        tarfile_file_mock.extractall.assert_called_once_with(unpack_dir)

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_fileobj(self, is_within_directory_patch, tarfile_open_patch):
        stream_str = io.BytesIO(b"Hello World!")
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = True

        tarfile_file_mock = Mock()  # Mock tarfile
        tar_file_obj_mock = Mock()  # Mock member inside tarfile
        tar_file_obj_mock.name = "obj_name"
        tarfile_file_mock.getmembers.return_value = [tar_file_obj_mock]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(file_obj=stream_str, unpack_dir=unpack_dir)

        is_within_directory_patch.assert_called_once()
        tarfile_file_mock.getmembers.assert_called_once()
        tarfile_file_mock.extractall.assert_called_once_with(unpack_dir)

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_obj_not_within_dir(self, is_within_directory_patch, tarfile_open_patch):
        tarfile_path = "/test_tarfile_path/"
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = False

        tarfile_file_mock = Mock()
        tar_file_obj_mock = Mock()
        tar_file_obj_mock.name = "obj_name"
        tarfile_file_mock.getmembers.return_value = [tar_file_obj_mock]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        with self.assertRaises(tarfile.ExtractError):
            extract_tarfile(tarfile_path=tarfile_path, unpack_dir=unpack_dir)

        is_within_directory_patch.assert_called_once()
        tarfile_file_mock.getmembers.assert_called_once()

    def test_tarfile_obj_is_within_dir(self):
        directory = "/my/path"
        target = "/my/path/file"

        self.assertTrue(_is_within_directory(directory, target))

    def test_tarfile_obj_is_not_within_dir(self):
        directory = "/my/path"
        target = "/another/path/file"

        self.assertFalse(_is_within_directory(directory, target))
