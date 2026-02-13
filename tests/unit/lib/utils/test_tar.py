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
        tar_file_obj_mock.issym.return_value = False
        tarfile_file_mock.getmembers.return_value = [tar_file_obj_mock]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(tarfile_path=tarfile_path, unpack_dir=unpack_dir)

        is_within_directory_patch.assert_called_once()
        tarfile_file_mock.getmembers.assert_called_once()
        tarfile_file_mock.extractall.assert_called_once_with(unpack_dir, members=[tar_file_obj_mock])

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_fileobj(self, is_within_directory_patch, tarfile_open_patch):
        stream_str = io.BytesIO(b"Hello World!")
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = True

        tarfile_file_mock = Mock()  # Mock tarfile
        tar_file_obj_mock = Mock()  # Mock member inside tarfile
        tar_file_obj_mock.name = "obj_name"
        tar_file_obj_mock.issym.return_value = False
        tarfile_file_mock.getmembers.return_value = [tar_file_obj_mock]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(file_obj=stream_str, unpack_dir=unpack_dir)

        is_within_directory_patch.assert_called_once()
        tarfile_file_mock.getmembers.assert_called_once()
        tarfile_file_mock.extractall.assert_called_once_with(unpack_dir, members=[tar_file_obj_mock])

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_obj_not_within_dir(self, is_within_directory_patch, tarfile_open_patch):
        tarfile_path = "/test_tarfile_path/"
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = False

        tarfile_file_mock = Mock()
        tar_file_obj_mock = Mock()
        tar_file_obj_mock.name = "obj_name"
        tar_file_obj_mock.issym.return_value = False
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

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    def test_extract_tarfile_allows_safe_symlinks(self, is_within_directory_patch, tarfile_open_patch):
        # All paths are within directory
        tarfile_path = "/test_tarfile_path/"
        unpack_dir = "/test_unpack_dir/"
        is_within_directory_patch.return_value = True

        tarfile_file_mock = Mock()

        regular_file_1 = Mock()
        regular_file_1.name = "regular_file_1.txt"
        regular_file_1.issym.return_value = False

        safe_symlink = Mock()
        safe_symlink.name = "safe_symlink"
        safe_symlink.linkname = "regular_file_1.txt"
        safe_symlink.issym.return_value = True

        regular_file_2 = Mock()
        regular_file_2.name = "regular_file_2.txt"
        regular_file_2.issym.return_value = False

        tarfile_file_mock.getmembers.return_value = [regular_file_1, safe_symlink, regular_file_2]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(tarfile_path=tarfile_path, unpack_dir=unpack_dir)

        tarfile_file_mock.extractall.assert_called_once()
        call_args = tarfile_file_mock.extractall.call_args
        extracted_members = call_args[1]["members"]

        self.assertEqual(len(extracted_members), 3)
        self.assertIn(regular_file_1, extracted_members)
        self.assertIn(safe_symlink, extracted_members)
        self.assertIn(regular_file_2, extracted_members)

    @patch("samcli.lib.utils.tar.tarfile.open")
    @patch("samcli.lib.utils.tar._is_within_directory")
    @patch("samcli.lib.utils.tar.LOG")
    def test_extract_tarfile_skips_unsafe_symlinks(self, log_mock, is_within_directory_patch, tarfile_open_patch):
        tarfile_path = "/test_tarfile_path/"
        unpack_dir = "/test_unpack_dir/"

        # Mock to return False only for the symlink target path
        def is_within_side_effect(directory, target):
            # Unsafe symlink target is outside directory
            if "outside_target" in target:
                return False
            return True

        is_within_directory_patch.side_effect = is_within_side_effect

        tarfile_file_mock = Mock()

        regular_file_1 = Mock()
        regular_file_1.name = "regular_file_1.txt"
        regular_file_1.issym.return_value = False

        unsafe_symlink = Mock()
        unsafe_symlink.name = "unsafe_symlink"
        unsafe_symlink.linkname = "../../../outside_target"
        unsafe_symlink.issym.return_value = True

        regular_file_2 = Mock()
        regular_file_2.name = "regular_file_2.txt"
        regular_file_2.issym.return_value = False

        tarfile_file_mock.getmembers.return_value = [regular_file_1, unsafe_symlink, regular_file_2]
        tarfile_open_patch.return_value.__enter__.return_value = tarfile_file_mock

        extract_tarfile(tarfile_path=tarfile_path, unpack_dir=unpack_dir)

        log_mock.warning.assert_called_once()
        warning_call = log_mock.warning.call_args[0]
        self.assertIn("Skipping symbolic link", warning_call[0])
        self.assertIn("unsafe_symlink", warning_call[1])

        tarfile_file_mock.extractall.assert_called_once()
        call_args = tarfile_file_mock.extractall.call_args
        extracted_members = call_args[1]["members"]

        self.assertEqual(len(extracted_members), 2)
        self.assertIn(regular_file_1, extracted_members)
        self.assertIn(regular_file_2, extracted_members)
        self.assertNotIn(unsafe_symlink, extracted_members)
