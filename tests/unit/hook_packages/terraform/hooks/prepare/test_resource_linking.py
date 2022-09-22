from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    _clean_references_list,
    _get_configuration_address,
    TFModule,
    TFResource,
    ConstantValue,
    References,
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
