from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, patch

from parameterized import parameterized
from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidResourceLinkingException

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    ResolvedReference,
    _clean_references_list,
    _get_configuration_address,
    _resolve_module_output,
    TFModule,
    TFResource,
    References,
    ConstantValue,
)


class TestResourceLinking(TestCase):
    @parameterized.expand(
        [
            ([], []),
            (["aws_lambda_layer_version.layer1[0].arn"], ["aws_lambda_layer_version.layer1[0].arn"]),
            (["aws_lambda_layer_version.layer1[0]"], ["aws_lambda_layer_version.layer1[0]"]),
            (["aws_lambda_layer_version.layer1"], ["aws_lambda_layer_version.layer1"]),
            (
                [
                    "aws_lambda_layer_version.layer1[0].arn",
                    "aws_lambda_layer_version.layer1[0]",
                    "aws_lambda_layer_version.layer1",
                ],
                ["aws_lambda_layer_version.layer1[0].arn"],
            ),
            (
                [
                    "aws_lambda_layer_version.layer1[0].arn",
                    "aws_lambda_layer_version.layer1[0]",
                    "aws_lambda_layer_version.layer1",
                    "module.const_layer1.layer_arn",
                    "module.const_layer1",
                    "module.const_layer2.layer_arn",
                    "module.const_layer2",
                ],
                [
                    "module.const_layer2.layer_arn",
                    "module.const_layer1.layer_arn",
                    "aws_lambda_layer_version.layer1[0].arn",
                ],
            ),
            (
                [
                    'aws_lambda_layer_version.layer1["key1"].arn',
                    'aws_lambda_layer_version.layer1["key1"]',
                    "aws_lambda_layer_version.layer1",
                ],
                ['aws_lambda_layer_version.layer1["key1"].arn'],
            ),
        ]
    )
    def test_clean_references_list(self, references, expected):
        cleaned_references = _clean_references_list(references)
        self.assertEqual(cleaned_references, expected)

    def test_ensure_original_references_not_mutated(self):
        references = [
            "aws_lambda_layer_version.layer1[0].arn",
            "aws_lambda_layer_version.layer1[0]",
            "aws_lambda_layer_version.layer1",
            "module.const_layer1.layer_arn",
            "module.const_layer1",
            "module.const_layer2.layer_arn",
            "module.const_layer2",
        ]
        original_references = deepcopy(references)
        cleaned_references_list = _clean_references_list(references)
        self.assertEqual(references, original_references)
        self.assertNotEqual(references, cleaned_references_list)

    @parameterized.expand(
        [
            (
                "module.get_language_function.aws_lambda_function.this[0]",
                "module.get_language_function.aws_lambda_function.this",
            ),
            (
                "module.get_language_function.aws_lambda_function.this[1]",
                "module.get_language_function.aws_lambda_function.this",
            ),
            ("module.functions[0].aws_lambda_function.this[0]", "module.functions.aws_lambda_function.this"),
            ("module.functions[1].aws_lambda_function.this[1]", "module.functions.aws_lambda_function.this"),
            (
                'module.functions["get_function"].aws_lambda_function.this[0]',
                "module.functions.aws_lambda_function.this",
            ),
            (
                "module.functions.aws_lambda_function.this",
                "module.functions.aws_lambda_function.this",
            ),
        ]
    )
    def test_get_configation_address(self, input_addr, expected_addr):
        cleaned_addr = _get_configuration_address(input_addr)

        self.assertEqual(cleaned_addr, expected_addr)

    def test_module_get_all_resources(self):
        root_module_resources = [Mock(), Mock()]
        child_module1_resources = [Mock(), Mock()]
        child_module2_resources = [Mock(), Mock()]
        grandchild_module_resources = [Mock(), Mock()]

        root_module = TFModule(None, None, {}, root_module_resources, {}, {})
        child_module1 = TFModule("module.child_module1", root_module, {}, child_module1_resources, {}, {})
        child_module2 = TFModule("module.child_module2", root_module, {}, child_module2_resources, {}, {})
        grandchild_module = TFModule(
            "module.child_module.grandchild_module", child_module1, {}, grandchild_module_resources, {}, {}
        )

        root_module.child_modules.update({"child_module1": child_module1, "child_module2": child_module2})
        child_module1.child_modules.update({"grandchild_module": grandchild_module})

        self.assertCountEqual(
            root_module.get_all_resources(),
            root_module_resources + child_module1_resources + child_module2_resources + grandchild_module_resources,
        )

    def test_resource_full_address(self):
        module = TFModule("module.full_address", None, {}, {}, {}, {})
        resource = TFResource("resource_address", "type", module, {})
        self.assertEqual(resource.full_address, "module.full_address.resource_address")

    def test_resource_full_address_root_module(self):
        module = TFModule(None, None, {}, {}, {}, {})
        resource = TFResource("resource_address", "type", module, {})
        self.assertEqual(resource.full_address, "resource_address")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_variable")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_with_var(self, clean_ref_mock, config_mock, resolve_var_mock):
        module = TFModule(
            None,
            None,
            {"mycoolref": ConstantValue("mycoolvar")},
            [],
            {},
            {"mycooloutput": References(["var.mycoolref"])},
        )

        config_mock.return_value = "mycoolref"
        clean_ref_mock.return_value = ["var.mycoolref"]

        _resolve_module_output(module, "mycooloutput")

        config_mock.assert_called_with("mycoolref")
        resolve_var_mock.assert_called_with(module, "mycoolref")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_with_module(self, clean_ref_mock, config_mock):
        module = TFModule(None, None, {}, [], {}, {"mycooloutput": References(["module.mycoolmod.mycooloutput2"])})
        module2 = TFModule("module.mycoolmod", module, {}, [], {}, {"mycooloutput2": ConstantValue("mycoolconst")})
        module.child_modules.update({"mycoolmod": module2})

        config_mock.return_value = "mycoolmod"
        clean_ref_mock.return_value = ["module.mycoolmod.mycooloutput2"]

        results = _resolve_module_output(module, "mycooloutput")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "mycoolconst")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_already_resolved_constant(self, clean_ref_mock, config_mock):
        module = TFModule(None, None, {}, [], {}, {"mycooloutput": ConstantValue("mycoolconst")})

        results = _resolve_module_output(module, "mycooloutput")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "mycoolconst")
        self.assertIsInstance(results[0], ConstantValue)

    @parameterized.expand(
        [
            (
                TFModule("module.name", None, {}, [], {}, {"mycooloutput": References(["local.mycoolconst"])}),
                "module.name",
            ),
            (TFModule(None, None, {}, [], {}, {"mycooloutput": References(["local.mycoolconst"])}), ""),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_already_resolved_reference(self, module, expected_addr, clean_ref_mock, config_mock):
        clean_ref_mock.return_value = ["local.mycoolconst"]

        results = _resolve_module_output(module, "mycooloutput")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "local.mycoolconst")
        self.assertEqual(results[0].module_address, expected_addr)
        self.assertIsInstance(results[0], ResolvedReference)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_raises_exception_empty_output(self, clean_ref_mock, get_config_mock):
        module = TFModule("module.mymod", None, {}, [], {}, {})

        with self.assertRaises(InvalidResourceLinkingException) as err:
            _resolve_module_output(module, "empty")

        self.assertEqual(
            str(err.exception),
            "An error occurred when attempting to link two resources: Output empty was not found in module module.mymod",
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_raises_exception_empty_children(self, clean_ref_mock, get_config_mock):
        module = TFModule("module.mymod", None, {}, [], {}, {"search": References(["module.nonexist.output"])})

        clean_ref_mock.return_value = ["module.nonexist"]
        get_config_mock.return_value = "nonexist"

        with self.assertRaises(InvalidResourceLinkingException) as err:
            _resolve_module_output(module, "search")

        self.assertEqual(
            str(err.exception),
            "An error occurred when attempting to link two resources: Module module.mymod does not have child modules defined, possible misconfiguration",
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_raises_exception_non_exist_child(self, clean_ref_mock, get_config_mock):
        module = TFModule(
            "module.mymod", None, {}, [], {"othermod": Mock()}, {"search": References(["module.nonexist.output"])}
        )
        clean_ref_mock.return_value = ["module.nonexist.output"]
        get_config_mock.return_value = "nonexist"

        with self.assertRaises(InvalidResourceLinkingException) as err:
            _resolve_module_output(module, "search")

        self.assertEqual(
            str(err.exception),
            "An error occurred when attempting to link two resources: Module module.mymod does not have nonexist as a child module, possible misconfiguration",
        )
