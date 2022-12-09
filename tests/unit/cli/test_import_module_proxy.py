import importlib
from unittest import TestCase

from parameterized import parameterized

from samcli.cli import hidden_imports
from samcli.cli.import_module_proxy import attach_import_module_proxy, MissingDynamicImportError


class TestImportModuleProxy(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        attach_import_module_proxy()

    def test_import_should_succeed_for_a_package_not_under_samcli(self):
        importlib.import_module("aws_lambda_builders.workflows.custom_make.workflow")

    @parameterized.expand(hidden_imports.SAM_CLI_HIDDEN_IMPORTS)
    def test_import_should_succeed_for_a_defined_hidden_package(self, package):
        try:
            importlib.import_module(package)
        except ModuleNotFoundError as ex:
            # pkg_resources.py2_warn is required for pyinstaller, and it is not available in SAM CLI
            # for this reason, skip any failures related to that package
            if "No module named 'pkg_resources.py2_warn'" not in ex.msg:
                raise ex

    def test_import_should_fail_for_undefined_hidden_package(self):
        with self.assertRaises(MissingDynamicImportError):
            importlib.import_module("samcli.yamlhelper")
