import importlib
from unittest import TestCase, skipIf

from parameterized import parameterized

from samcli.cli import hidden_imports
from samcli.cli.import_module_proxy import (
    attach_import_module_proxy,
    MissingDynamicImportError,
)
from tests.testing_utils import IS_WINDOWS


@skipIf(IS_WINDOWS, "Skip dynamic import tests for Windows as we don't use PyInstaller for it")
class TestImportModuleProxy(TestCase):
    """
    There is a chance that setUpClass method of this test class might cause flakiness with other tests if we run them
    in parallel.
    """

    original_import_module = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.original_import_module = importlib.import_module
        attach_import_module_proxy()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.original_import_module:
            importlib.import_module = cls.original_import_module

    @parameterized.expand(hidden_imports.SAM_CLI_HIDDEN_IMPORTS)
    def test_import_should_succeed_for_a_defined_hidden_package(self, package):
        if package == "samcli.hook_packages.terraform.copy_terraform_built_artifacts":
            self.skipTest(
                "Copy Terraform built artifacts script will not be imported in sam cli, but will be executed as a standalone script and does not require any non standard modules"
            )
        try:
            importlib.import_module(package)
        except ModuleNotFoundError as ex:
            # pkg_resources.py2_warn is required for pyinstaller, and it is not available in SAM CLI
            # for this reason, skip any failures related to that package
            if "No module named 'pkg_resources.py2_warn'" not in ex.msg:
                raise ex

    def test_import_should_fail_for_undefined_hidden_package(self):
        with self.assertRaises(MissingDynamicImportError):
            importlib.import_module("some.other.module")
