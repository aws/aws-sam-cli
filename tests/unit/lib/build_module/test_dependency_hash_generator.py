import os
import shutil
import tempfile
from pathlib import Path
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


class TestDependencyHashGeneratorPythonUv(TestCase):
    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base_dir)
        self.function_dir = Path(self.base_dir, "fn")
        self.function_dir.mkdir()

    def write(self, relative_path, content):
        path = Path(self.base_dir, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def uv_hash(self, code_uri="fn", runtime="python3.12", build_method="python-uv", base_dir=None):
        return DependencyHashGenerator(code_uri, base_dir or self.base_dir, runtime, build_method=build_method).hash

    def test_project_without_requirements_txt_gets_a_hash(self):
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        self.write("fn/uv.lock", "lock-1")
        self.assertIsNotNone(self.uv_hash())
        # the pip workflow found no requirements.txt here, so this used to be None
        self.assertIsNone(self.uv_hash(build_method=None))

    def test_hash_changes_with_lock_and_pyproject(self):
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        self.write("fn/uv.lock", "lock-1")
        original = self.uv_hash()
        self.assertEqual(self.uv_hash(), original)

        self.write("fn/uv.lock", "lock-2")
        after_lock_change = self.uv_hash()
        self.assertNotEqual(after_lock_change, original)

        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six", "attrs"]\n')
        self.assertNotEqual(self.uv_hash(), after_lock_change)

    def test_workspace_member_hashes_root_lock_and_root_pyproject(self):
        self.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["fn"]\n')
        self.write("uv.lock", "lock-1")
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        original = self.uv_hash()

        self.write("uv.lock", "lock-2")
        after_lock_change = self.uv_hash()
        self.assertNotEqual(after_lock_change, original)

        self.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["fn", "lib"]\n')
        self.assertNotEqual(self.uv_hash(), after_lock_change)

    def test_requirements_manifest_ignores_lock(self):
        self.write("fn/requirements.txt", "six\n")
        self.write("fn/uv.lock", "lock-1")
        original = self.uv_hash()
        self.assertIsNotNone(original)

        self.write("fn/uv.lock", "lock-2")
        self.assertEqual(self.uv_hash(), original)

        self.write("fn/requirements.txt", "six\nattrs\n")
        self.assertNotEqual(self.uv_hash(), original)

    def test_no_manifest_returns_none(self):
        self.assertIsNone(self.uv_hash())

    def test_layer_build_method_passed_as_runtime(self):
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        self.write("fn/uv.lock", "lock-1")
        self.assertEqual(self.uv_hash(runtime="python-uv", build_method=None), self.uv_hash())

    def test_hash_is_stable_when_project_moves(self):
        self.write("pyproject.toml", '[tool.uv.workspace]\nmembers = ["fn"]\n')
        self.write("uv.lock", "lock-1")
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        moved = os.path.join(tempfile.mkdtemp(), "moved")
        self.addCleanup(shutil.rmtree, os.path.dirname(moved))
        shutil.copytree(self.base_dir, moved)
        self.assertEqual(self.uv_hash(base_dir=moved), self.uv_hash())

    def test_manifest_override_wins(self):
        self.write("fn/pyproject.toml", '[project]\nname = "fn"\ndependencies = ["six"]\n')
        self.write("fn/uv.lock", "lock-1")
        self.write("fn/other.txt", "six\n")
        generator = DependencyHashGenerator(
            "fn", self.base_dir, "python3.12", manifest_path_override="other.txt", build_method="python-uv"
        )
        before = generator.hash
        self.write("fn/uv.lock", "lock-2")
        after = DependencyHashGenerator(
            "fn", self.base_dir, "python3.12", manifest_path_override="other.txt", build_method="python-uv"
        ).hash
        self.assertEqual(before, after)
