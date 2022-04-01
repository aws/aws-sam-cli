from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.lib.build.dependency_hash_generator import DependencyHashGenerator


class TestDependencyHashGenerator(TestCase):
    def setUp(self):
        self.get_workflow_config_patch = patch("samcli.lib.build.dependency_hash_generator.get_workflow_config")
        self.get_workflow_config_mock = self.get_workflow_config_patch.start()
        self.get_workflow_config_mock.return_value.manifest_name = "manifest_file"

        self.file_checksum_patch = patch("samcli.lib.build.dependency_hash_generator.file_checksum")
        self.file_checksum_mock = self.file_checksum_patch.start()
        self.file_checksum_mock.return_value = "checksum"

    def tearDown(self):
        self.get_workflow_config_patch.stop()
        self.file_checksum_patch.stop()

    @patch("samcli.lib.build.dependency_hash_generator.DependencyHashGenerator._calculate_dependency_hash")
    @patch("samcli.lib.build.dependency_hash_generator.pathlib.Path")
    def test_init_and_properties(self, path_mock, calculate_hash_mock):
        path_mock.return_value.resolve.return_value.__str__.return_value = "code_dir"
        calculate_hash_mock.return_value = "dependency_hash"
        self.generator = DependencyHashGenerator("code_uri", "base_dir", "runtime")
        self.assertEqual(self.generator._code_uri, "code_uri")
        self.assertEqual(self.generator._base_dir, "base_dir")
        self.assertEqual(self.generator._code_dir, "code_dir")
        self.assertEqual(self.generator._runtime, "runtime")
        self.assertEqual(self.generator.hash, "dependency_hash")

        path_mock.assert_called_once_with("base_dir", "code_uri")

    @patch("samcli.lib.build.dependency_hash_generator.pathlib.Path")
    def test_calculate_manifest_hash(self, path_mock):
        code_dir_mock = MagicMock()
        code_dir_mock.resolve.return_value.__str__.return_value = "code_dir"
        manifest_path_mock = MagicMock()
        manifest_path_mock.resolve.return_value.__str__.return_value = "manifest_path"
        manifest_path_mock.resolve.return_value.is_file.return_value = True
        path_mock.side_effect = [code_dir_mock, manifest_path_mock]

        self.generator = DependencyHashGenerator("code_uri", "base_dir", "runtime")
        hash = self.generator.hash
        self.file_checksum_mock.assert_called_once_with("manifest_path", hash_generator=None)
        self.assertEqual(hash, "checksum")

        path_mock.assert_any_call("base_dir", "code_uri")
        path_mock.assert_any_call("code_dir", "manifest_file")

    @patch("samcli.lib.build.dependency_hash_generator.pathlib.Path")
    def test_calculate_manifest_hash_missing_file(self, path_mock):
        code_dir_mock = MagicMock()
        code_dir_mock.resolve.return_value.__str__.return_value = "code_dir"
        manifest_path_mock = MagicMock()
        manifest_path_mock.resolve.return_value.__str__.return_value = "manifest_path"
        manifest_path_mock.resolve.return_value.is_file.return_value = False
        path_mock.side_effect = [code_dir_mock, manifest_path_mock]

        self.generator = DependencyHashGenerator("code_uri", "base_dir", "runtime")
        self.file_checksum_mock.assert_not_called()
        self.assertEqual(self.generator.hash, None)

        path_mock.assert_any_call("base_dir", "code_uri")
        path_mock.assert_any_call("code_dir", "manifest_file")

    @patch("samcli.lib.build.dependency_hash_generator.pathlib.Path")
    def test_calculate_manifest_hash_manifest_override(self, path_mock):
        code_dir_mock = MagicMock()
        code_dir_mock.resolve.return_value.__str__.return_value = "code_dir"
        manifest_path_mock = MagicMock()
        manifest_path_mock.resolve.return_value.__str__.return_value = "manifest_path"
        manifest_path_mock.resolve.return_value.is_file.return_value = True
        path_mock.side_effect = [code_dir_mock, manifest_path_mock]

        self.generator = DependencyHashGenerator(
            "code_uri", "base_dir", "runtime", manifest_path_override="manifest_override"
        )
        hash = self.generator.hash
        self.get_workflow_config_mock.assert_not_called()
        self.file_checksum_mock.assert_called_once_with("manifest_path", hash_generator=None)
        self.assertEqual(hash, "checksum")

        path_mock.assert_any_call("base_dir", "code_uri")
        path_mock.assert_any_call("code_dir", "manifest_override")
