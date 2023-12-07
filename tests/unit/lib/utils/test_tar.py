import io
from unittest import TestCase
import tarfile
from unittest.mock import MagicMock, Mock, patch, call
from parameterized import parameterized

from samcli.lib.utils.tar import _validate_destinations_exists, extract_tarfile, create_tarball, _is_within_directory


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
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w", dereference=False)

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
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w:gz", dereference=False)

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
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w", dereference=False)

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

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar.TemporaryFile")
    @patch("samcli.lib.utils.tar._validate_destinations_exists")
    def test_generating_tarball_revert_false_derefernce(self, validate_mock, temporary_file_patch, tarfile_open_patch):
        temp_file_mock = Mock()
        temporary_file_patch.return_value = temp_file_mock

        tarfile_file_mock = Mock()
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        validate_mock.return_value = False

        # pass in dereference is True
        with create_tarball({"/some/path": "/layer1"}, tar_filter=None, dereference=True) as tarball:
            self.assertEqual(tarball, temp_file_mock)

        # validate that deference was changed back to False
        tarfile_open_patch.assert_called_once_with(fileobj=temp_file_mock, mode="w", dereference=False)

    @parameterized.expand(
        [
            (True,),
            (False,),
        ]
    )
    @patch("samcli.lib.utils.tar.Path")
    def test_validating_symlinked_tar_path(self, does_resolved_exist, path_mock):
        mock_resolved_object = Mock()
        mock_resolved_object.exists.return_value = does_resolved_exist

        mock_path_object = Mock()
        mock_path_object.resolve = Mock()
        mock_path_object.resolve.return_value = mock_resolved_object
        mock_path_object.is_symlink = Mock()
        mock_path_object.is_symlink.return_value = True
        mock_path_object.is_dir.return_value = False

        path_mock.return_value = mock_path_object

        result = _validate_destinations_exists(["mock_path"])

        self.assertEqual(result, does_resolved_exist)

    @parameterized.expand(
        [
            (True,),
            (False,),
        ]
    )
    @patch("samcli.lib.utils.tar.Path")
    def test_validating_symlinked_tar_path_directory(self, file_exists, path_mock):
        mock_child_resolve = Mock()
        mock_child_resolve.exists.return_value = file_exists

        mock_child = Mock()
        mock_child.is_symlink.return_value = True
        mock_child.is_dir.return_value = False
        mock_child.resolve.return_value = mock_child_resolve

        mock_dir_object = Mock()
        mock_dir_object.is_symlink.return_value = False
        mock_dir_object.is_dir.return_value = True
        mock_dir_object.iterdir.return_value = ["mock_child"]
        mock_dir_object.resolve = Mock()

        path_mock.side_effect = [mock_dir_object, mock_child]

        result = _validate_destinations_exists(["mock_folder"])

        self.assertEqual(result, file_exists)
