from pathlib import Path
from unittest import TestCase

from installer.pyinstaller import hidden_imports
from samcli.cli.command import BaseCommand
from samcli.lib.hook.hook_wrapper import get_available_hook_packages_ids


class TestPyinstallerHiddenImports(TestCase):
    def setUp(self):
        pass

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


class TestGetSamcliModules(TestCase):
    SAMCLI_ROOT = Path(__file__).parent.parent.parent.parent / "samcli"

    @classmethod
    def setUpClass(cls):
        samcli_root = cls.SAMCLI_ROOT
        my_test_module = samcli_root / "my_test_module"
        my_test_module.mkdir(exist_ok=True)
        (my_test_module / "__init__.py").touch(exist_ok=True)
        (my_test_module / "my_submodule.py").touch(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        samcli_root = cls.SAMCLI_ROOT
        my_test_module = samcli_root / "my_test_module"
        (my_test_module / "__init__.py").unlink()
        (my_test_module / "my_submodule.py").unlink()
        my_test_module.rmdir()

    def test_samcli_modules_contain_dir_module(self):
        self.assertIn("samcli.my_test_module", hidden_imports.get_samcli_modules())

    def test_samcli_modules_contain_file_module(self):
        self.assertIn("samcli.my_test_module.my_submodule", hidden_imports.get_samcli_modules())

    def test_samcli_modules_not_contain_nonexistant_module(self):
        self.assertNotIn("my_non_existant_module", hidden_imports.get_samcli_modules())
