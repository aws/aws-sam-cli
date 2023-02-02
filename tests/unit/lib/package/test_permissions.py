import zipfile

from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.package.permissions import (
    WindowsFilePermissionMapper,
    WindowsDirPermissionMapper,
    AdditiveFilePermissionMapper,
    AdditiveDirPermissionMapper,
)


class TestPermissions(TestCase):
    @patch("platform.system")
    def test_file_permission_mapper_linux(self, mock_system):
        mock_system.return_value = "Linux"
        # permissions set are ignored.
        mapper = WindowsFilePermissionMapper(permissions=0o100777)
        zi = zipfile.ZipInfo()
        self.assertEqual(mapper.apply(zi), zi)
        # return as-is
        self.assertNotEqual(zi.external_attr, mapper.permissions << 16)

    @patch("platform.system")
    def test_dir_permission_mapper_linux(self, mock_system):
        mock_system.return_value = "Linux"
        # permissions set are ignored.
        mapper = WindowsDirPermissionMapper(permissions=0o100777)
        zi = zipfile.ZipInfo(filename="dir/")
        self.assertEqual(mapper.apply(zi), zi)
        # return as-is
        self.assertNotEqual(zi.external_attr, mapper.permissions << 16)

    @patch("platform.system")
    def test_file_permission_mapper_windows(self, mock_system):
        mock_system.return_value = "Windows"
        mapper = WindowsFilePermissionMapper(permissions=0o100644)
        zi = zipfile.ZipInfo()
        self.assertEqual(mapper.apply(zi).external_attr, mapper.permissions << 16)

    @patch("platform.system")
    def test_dir_permission_mapper_windows(self, mock_system):
        mock_system.return_value = "Windows"
        mapper = WindowsDirPermissionMapper(permissions=0o100755)
        zi = zipfile.ZipInfo(filename="dir/")
        self.assertEqual(mapper.apply(zi).external_attr, mapper.permissions << 16)

    @parameterized.expand(
        [
            (AdditiveFilePermissionMapper, "file", 0o100000, 0o100444, 0o100444),
            (AdditiveFilePermissionMapper, "file", 0o100111, 0o100444, 0o100555),
            (AdditiveFilePermissionMapper, "file", 0o100444, 0o100444, 0o100444),
            (AdditiveFilePermissionMapper, "file", 0o100644, 0o100444, 0o100644),
            (AdditiveFilePermissionMapper, "file", 0o100777, 0o100444, 0o100777),
            (AdditiveDirPermissionMapper, "dir/", 0o100000, 0o100111, 0o100111),
            (AdditiveDirPermissionMapper, "dir/", 0o100111, 0o100444, 0o100555),
            (AdditiveDirPermissionMapper, "dir/", 0o100111, 0o100111, 0o100111),
            (AdditiveDirPermissionMapper, "dir/", 0o100644, 0o100111, 0o100755),
            (AdditiveDirPermissionMapper, "dir/", 0o100777, 0o100111, 0o100777),
        ]
    )
    def test_additive_permissions(
        self, _mapper, filename, current_permissions, additive_permissions, resultant_permissions
    ):
        mapper = _mapper(permissions=additive_permissions)
        zi = zipfile.ZipInfo(filename=filename)
        zi.external_attr = current_permissions << 16
        self.assertEqual(mapper.apply(zi).external_attr, resultant_permissions << 16)
