import tempfile
import sys
from pathlib import Path
from unittest import TestCase

from samcli.cli import hidden_imports
from samcli.cli.command import BaseCommand
from samcli.lib.hook.hook_wrapper import get_available_hook_packages_ids


class TestPyinstallerHiddenImports(TestCase):
    def test_hook_contains_all_default_command_packages(self):
        cmd = BaseCommand()
        command_package_names = cmd._commands.values()

        for name in command_package_names:
            self.assertIn(name, hidden_imports.SAM_CLI_HIDDEN_IMPORTS)

    def test_hook_not_contain_self_defined_command_packages(self):
        cmd = BaseCommand(cmd_packages=["my.self.defined.package"])
        command_package_names = cmd._commands.values()

        for name in command_package_names:
            self.assertNotIn(name, hidden_imports.SAM_CLI_HIDDEN_IMPORTS)

    def test_hook_contain_all_samcli_hook_packages(self):
        hook_package_modules = [f"samcli.hook_packages.{hook_name}" for hook_name in get_available_hook_packages_ids()]
        for module in hook_package_modules:
            self.assertIn(module, hidden_imports.SAM_CLI_HIDDEN_IMPORTS)


class TestWalkModules(TestCase):
    def setUp(self):
        # create a temp modules
        temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir = temp_dir
        sys.path.append(self.temp_dir.name)
        temp_dir_path = Path(temp_dir.name)
        (temp_dir_path / "my_test_module").mkdir()
        (temp_dir_path / "my_test_module" / "__init__.py").touch()
        (temp_dir_path / "my_test_module" / "my_submodule").mkdir()
        (temp_dir_path / "my_test_module" / "my_submodule" / "__init__.py").touch()
        (temp_dir_path / "my_test_module" / "another_submodule.py").touch()

    def tearDown(self):
        sys.path.remove(self.temp_dir.name)
        self.temp_dir.cleanup()

    def test_walk_modules_contains_all_modules(self):
        my_test_module = __import__("my_test_module")
        modules = set(["my_test_module"])
        hidden_imports.walk_modules(my_test_module, modules)
        self.assertIn("my_test_module", modules)
        self.assertIn("my_test_module.my_submodule", modules)
        self.assertIn("my_test_module.another_submodule", modules)
        del sys.modules["my_test_module"]

    def test_walk_modules_not_contain_nonexistent_module(self):
        my_test_module = __import__("my_test_module")
        modules = set("my_test_module")
        hidden_imports.walk_modules(my_test_module, modules)
        self.assertNotIn("my_non_existant_module", modules)
        del sys.modules["my_test_module"]
