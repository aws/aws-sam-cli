import os
from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, patch, call
from uuid import uuid4

from parameterized import parameterized
from samcli.hook_packages.terraform.hooks.prepare.exceptions import (
    InvalidResourceLinkingException,
    LocalVariablesLinkingLimitationException,
    ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK,
    LOCAL_VARIABLES_SUPPORT_ISSUE_LINK,
    OneLambdaLayerLinkingLimitationException,
    FunctionLayerLocalVariablesLinkingLimitationException,
)

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import (
    _clean_references_list,
    _get_configuration_address,
    _resolve_module_output,
    _resolve_module_variable,
    _build_module,
    _build_expression_from_configuration,
    _build_module_full_address,
    _build_child_modules_from_configuration,
    _build_module_outputs_from_configuration,
    _build_module_resources_from_configuration,
    _build_module_variables_from_configuration,
    _resolve_resource_attribute,
    ResourceLinkingPair,
    ResourcePairExceptions,
    LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX,
    LinkerIntrinsics,
    ResourceLinker,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    ConstantValue,
    References,
    ResolvedReference,
    TFModule,
    TFResource,
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

        root_module = TFModule(None, None, {}, {str(uuid4()): resource for resource in root_module_resources}, {}, {})
        child_module1 = TFModule(
            "module.child_module1",
            root_module,
            {},
            {str(uuid4()): resource for resource in child_module1_resources},
            {},
            {},
        )
        child_module2 = TFModule(
            "module.child_module2",
            root_module,
            {},
            {str(uuid4()): resource for resource in child_module2_resources},
            {},
            {},
        )
        grandchild_module = TFModule(
            "module.child_module.grandchild_module",
            child_module1,
            {},
            {str(uuid4()): resource for resource in grandchild_module_resources},
            {},
            {},
        )

        root_module.child_modules.update({"child_module1": child_module1, "child_module2": child_module2})
        child_module1.child_modules.update({"grandchild_module": grandchild_module})

        self.assertEqual(
            len(root_module.get_all_resources()),
            len(
                root_module_resources + child_module1_resources + child_module2_resources + grandchild_module_resources
            ),
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
        constant_val = ConstantValue("mycoolvar")

        module = TFModule(
            None,
            None,
            {"mycoolref": constant_val},
            [],
            {},
            {"mycooloutput": References(["var.mycoolref"])},
        )

        config_mock.return_value = "mycoolref"
        clean_ref_mock.return_value = ["var.mycoolref"]
        resolve_var_mock.return_value = [constant_val]

        results = _resolve_module_output(module, "mycooloutput")

        # assert we are calling the right funcs
        config_mock.assert_called_with("mycoolref")
        resolve_var_mock.assert_called_with(module, "mycoolref")

        # assert we still return valid results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "mycoolvar")
        self.assertIsInstance(results[0], ConstantValue)

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
                TFModule("module.name", None, {}, {}, {}, {"mycooloutput": References(["local.mycoolconst"])}),
                "module.name",
            ),
            (TFModule(None, None, {}, {}, {}, {"mycooloutput": References(["local.mycoolconst"])}), None),
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

        clean_ref_mock.return_value = ["module.nonexist.output"]
        get_config_mock.return_value = "nonexist"

        with self.assertRaises(InvalidResourceLinkingException) as err:
            _resolve_module_output(module, "search")

        self.assertEqual(
            str(err.exception),
            "An error occurred when attempting to link two resources: Module module.mymod does not have child modules defined",
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
            "An error occurred when attempting to link two resources: Module module.mymod does not have nonexist as a child module",
        )

    @parameterized.expand(
        [
            "module.",
            "module..",
            "module.....",
            "module.name",
            "module.name.output.again",
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_output_invalid_module_name(self, invalid_reference, clean_ref_mock, get_config_mock):
        module = TFModule("module.name", None, {}, [], {}, {"output1": References([invalid_reference])})
        clean_ref_mock.return_value = [invalid_reference]

        with self.assertRaises(InvalidResourceLinkingException) as err:
            _resolve_module_output(module, "output1")

        self.assertEqual(
            str(err.exception),
            f"An error occurred when attempting to link two resources: Module module.name contains an invalid reference {invalid_reference}",
        )

    def test_resolve_module_variable_constant_value(self):
        constant_value = ConstantValue(value="layer.arn")
        module = TFModule(
            variables={"layer": constant_value},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )
        results = _resolve_module_variable(module, "layer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "layer.arn")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_nested_variables(self, mock_clean_references, mock_get_configuration_address):
        references = ["var.layer_name"]
        mock_clean_references.return_value = references
        mock_get_configuration_address.return_value = "layer_name"
        references = References(value=references)
        constant_value = ConstantValue(value="layer.arn")
        parent_module = TFModule(
            variables={"layer_name": constant_value},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )
        child_module = TFModule(
            variables={"layer": references},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=parent_module,
        )
        results = _resolve_module_variable(child_module, "layer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "layer.arn")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_local_variable(self, mock_clean_references, mock_get_configuration_address):
        references = ["local.layer_arn"]
        mock_clean_references.return_value = references
        mock_get_configuration_address.return_value = "layer_arn"
        local_reference = References(value=references)
        parent_module = TFModule(
            variables={},
            resources=[],
            child_modules={},
            outputs={},
            full_address="full/address",
            parent_module=None,
        )
        module = TFModule(
            variables={"layer": local_reference},
            resources=[],
            child_modules={},
            outputs={},
            full_address="full/address",
            parent_module=parent_module,
        )
        results = _resolve_module_variable(module, "layer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "local.layer_arn")
        self.assertEqual(results[0].module_address, "full/address")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_output")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_nested_modules(
        self, mock_clean_references, mock_resolve_module_output, mock_get_configuration_address
    ):
        references = ["module.layer_module.layer_arn"]
        mock_resolve_module_output.return_value = [ConstantValue(value="layer_arn")]
        mock_clean_references.return_value = references
        mock_get_configuration_address.return_value = "layer_module"
        references = References(value=references)
        constant_value = ConstantValue(value="layer_arn")
        parent_module = TFModule(
            variables={"layer_name": constant_value},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )
        child_module = TFModule(
            variables={"layer": references},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=parent_module,
        )
        parent_module.child_modules.update({"layer_module": child_module})
        results = _resolve_module_variable(child_module, "layer")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, "layer_arn")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_output")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_combined_nested_modules(
        self, mock_clean_references, mock_resolve_module_output, mock_get_configuration_address
    ):
        references = ["module.layer_module.layer_arn", "var.layer_name_b"]
        mock_resolve_module_output.return_value = [ConstantValue(value="layer_arn_a")]
        mock_clean_references.return_value = references
        mock_get_configuration_address.side_effect = ["layer_module", "layer_name_b"]
        references = References(value=references)
        parent_module = TFModule(
            variables={
                "layer_name": ConstantValue(value="layer_arn_a"),
                "layer_name_b": ConstantValue(value="layer_arn_b"),
            },
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )
        child_module = TFModule(
            variables={"layer": references, "layer_name_c": ConstantValue(value="layer_arn_c")},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=parent_module,
        )
        parent_module.child_modules.update({"layer_module": child_module})
        results_a = _resolve_module_variable(child_module, "layer")
        results_b = _resolve_module_variable(child_module, "layer_name_c")
        self.assertEqual(len(results_a), 2)
        self.assertEqual(len(results_b), 1)
        self.assertEqual(
            results_a[0].value,
            "layer_arn_a",
        )
        self.assertEqual(
            results_a[1].value,
            "layer_arn_b",
        )
        self.assertEqual(results_b[0].value, "layer_arn_c")

    def test_resolve_module_variable_invalid_variable(self):
        constant_value = None
        module = TFModule(
            variables={"layer": constant_value},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )

        with self.assertRaises(InvalidResourceLinkingException) as ex:
            _resolve_module_variable(module, "layer")

        self.assertEqual(
            ex.exception.args[0],
            "An error occurred when attempting to link two resources: The variable "
            "layer could not be found in module root module.",
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_enters_invalid_state(self, mock_clean_references, mock_get_configuration_address):
        references = ["local.layer_arn"]
        mock_clean_references.return_value = references
        mock_get_configuration_address.return_value = "layer_arn"
        local_reference = References(value=references)
        module = TFModule(
            variables={"layer": local_reference},
            resources=[],
            child_modules={},
            outputs={},
            full_address="full/address",
            parent_module=None,
        )

        with self.assertRaises(InvalidResourceLinkingException) as ex:
            _resolve_module_variable(module, "layer")

        self.assertEqual(
            ex.exception.args[0],
            "An error occurred when attempting to link two resources: Resource linking entered an invalid state.",
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_module_variable_invalid_module_reference(
        self, mock_clean_references, mock_get_configuration_address
    ):
        references = ["module.layer_module"]
        mock_clean_references.return_value = references
        mock_get_configuration_address.return_value = "layer_module"
        references = References(value=references)
        child_module = TFModule(
            variables={"layer": references},
            resources=[],
            child_modules={},
            outputs={},
            full_address="",
            parent_module=None,
        )
        with self.assertRaises(InvalidResourceLinkingException) as ex:
            _resolve_module_variable(child_module, "layer")

        self.assertEqual(
            ex.exception.args[0],
            "An error occurred when attempting to link two resources: Couldn't find child module layer_module.",
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_module_full_address")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_module_variables_from_configuration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_module_resources_from_configuration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_module_outputs_from_configuration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_child_modules_from_configuration")
    def test_build_module(
        self,
        patched_build_child_modules_from_configuration,
        patched_build_module_outputs_from_configuration,
        patched_build_module_resources_from_configuration,
        patched_build_module_variables_from_configuration,
        patched_build_module_full_address,
    ):
        mock_full_address = Mock()
        patched_build_module_full_address.return_value = mock_full_address

        mock_variables = Mock()
        patched_build_module_variables_from_configuration.return_value = mock_variables

        mock_resources = Mock()
        patched_build_module_resources_from_configuration.return_value = mock_resources

        mock_outputs = Mock()
        patched_build_module_outputs_from_configuration.return_value = mock_outputs

        mock_child_modules = Mock()
        patched_build_child_modules_from_configuration.return_value = mock_child_modules

        result = _build_module(Mock(), Mock(), Mock(), Mock())
        expected_module = TFModule(
            mock_full_address, None, mock_variables, mock_resources, mock_child_modules, mock_outputs
        )

        self.assertEqual(result, expected_module)

    @parameterized.expand(
        [
            (None, None, None),
            ("some_module", None, "module.some_module"),
            ("some_module", "parent_module_address", "parent_module_address.module.some_module"),
        ]
    )
    def test_build_module_full_address(self, module_name, parent_module_address, expected_full_address):
        result = _build_module_full_address(module_name, parent_module_address)
        self.assertEqual(result, expected_full_address)

    def test_build_module_variables_from_configuration(self):
        module_configuration = {
            "variables": {
                "var1": {"default": "var1_default_value"},
                "var2": {"default": "var2_default_value"},
                "var3": {},
                "var4": {},
            },
        }

        input_variables = {
            "var2": ConstantValue("var2_input_value"),
            "var4": ConstantValue("var4_input_value"),
        }

        result = _build_module_variables_from_configuration(module_configuration, input_variables)

        self.assertEqual(result["var1"], ConstantValue("var1_default_value"))
        self.assertEqual(result["var2"], input_variables["var2"])
        self.assertEqual(result["var3"], ConstantValue(None))
        self.assertEqual(result["var4"], ConstantValue("var4_input_value"))

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_expression_from_configuration")
    def test_build_module_resources_from_configuration(
        self,
        patched_build_expression_from_configuration,
    ):
        mock_parsed_expression = Mock()
        patched_build_expression_from_configuration.return_value = mock_parsed_expression

        module_configuration = {
            "resources": [
                {
                    "address": "resource1_address",
                    "type": "resource1_type",
                    "expressions": {
                        "expression1": Mock(),
                        "expression2": Mock(),
                    },
                },
                {
                    "address": "resource2_address",
                    "type": "resource2_type",
                    "expressions": {
                        "expression3": Mock(),
                        "expression4": Mock(),
                    },
                },
            ]
        }

        mock_module = Mock()

        result = _build_module_resources_from_configuration(module_configuration, mock_module)

        expected_resources = {
            "resource1_address": TFResource(
                "resource1_address",
                "resource1_type",
                mock_module,
                {"expression1": mock_parsed_expression, "expression2": mock_parsed_expression},
            ),
            "resource2_address": TFResource(
                "resource2_address",
                "resource2_type",
                mock_module,
                {"expression3": mock_parsed_expression, "expression4": mock_parsed_expression},
            ),
        }

        self.assertEqual(result, expected_resources)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_expression_from_configuration")
    def test_build_module_outputs_from_configuration(
        self,
        patched_build_expression_from_configuration,
    ):
        parsed_expression = Mock()
        patched_build_expression_from_configuration.return_value = parsed_expression

        module_configuration = {
            "outputs": {
                "output1": {
                    "expression": Mock(),
                },
                "output2": {
                    "expression": Mock(),
                },
            }
        }

        result = _build_module_outputs_from_configuration(module_configuration)

        expected_outputs = {
            "output1": parsed_expression,
            "output2": parsed_expression,
        }

        self.assertEqual(result, expected_outputs)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_expression_from_configuration")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._build_module")
    def test_build_child_modules_from_configuration(
        self,
        patched_build_module,
        patched_build_expression_from_configuration,
    ):
        mock_parsed_expression = Mock()
        patched_build_expression_from_configuration.return_value = mock_parsed_expression

        child_built_modules = [Mock(), Mock()]
        patched_build_module.side_effect = child_built_modules

        mock_child_config1 = Mock()
        mock_child_config2 = Mock()
        module_configuration = {
            "module_calls": {
                "module1": {
                    "expressions": {
                        "expression1": Mock(),
                        "expression2": Mock(),
                    },
                    "module": mock_child_config1,
                },
                "module2": {
                    "expressions": {
                        "expression3": Mock(),
                        "expression4": Mock(),
                    },
                    "module": mock_child_config2,
                },
            },
        }

        mock_module = Mock(full_address="module.some_address")

        result = _build_child_modules_from_configuration(module_configuration, mock_module)

        # check it builds child modules
        patched_build_module.assert_has_calls(
            [
                call(
                    "module1",
                    mock_child_config1,
                    {"expression1": mock_parsed_expression, "expression2": mock_parsed_expression},
                    "module.some_address",
                ),
                call(
                    "module2",
                    mock_child_config2,
                    {"expression3": mock_parsed_expression, "expression4": mock_parsed_expression},
                    "module.some_address",
                ),
            ]
        )

        # check it sets parent module of each child
        for child in child_built_modules:
            self.assertEqual(child.parent_module, mock_module)

        # check return result
        self.assertCountEqual(list(result.keys()), ["module1", "module2"])
        self.assertCountEqual(list(result.values()), child_built_modules)

    @parameterized.expand(
        [
            ({"constant_value": "hello"}, ConstantValue("hello")),
            ({"references": ["hello", "world"]}, References(["hello", "world"])),
        ]
    )
    def test_build_expression_from_configuration(
        self,
        expression_configuration,
        expected_parsed_expression,
    ):
        result = _build_expression_from_configuration(expression_configuration)
        self.assertEqual(result, expected_parsed_expression)

    def test_resolve_resource_attribute_constant_value(self):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": ConstantValue(value=["layer1.arn", "layer2.arn"]),
            },
        )
        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].value, ["layer1.arn", "layer2.arn"])

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_variable")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    def test_resolve_resource_attribute_variable_reference(
        self, get_configuration_address_mock, clean_references_mock, resolve_module_variable_mock
    ):
        value1 = Mock()
        value2 = Mock()
        resolve_module_variable_mock.side_effect = [[value1], [value2]]
        clean_references_mock.return_value = ["var.layer_arn_1", "var.layer_arn_2"]
        get_configuration_address_mock.side_effect = ["layer_arn_1", "layer_arn_2"]

        parent_module = TFModule(None, None, {}, [], {}, {})
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=parent_module,
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["var.layer_arn_1", "var.layer_arn_2"]),
            },
        )
        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], value1)
        self.assertEqual(results[1], value2)
        get_configuration_address_mock.has_calls([call("layer_arn_1"), call("layer_arn_2")])
        resolve_module_variable_mock.assert_has_calls(
            [
                call(
                    parent_module,
                    "layer_arn_1",
                ),
                call(
                    parent_module,
                    "layer_arn_2",
                ),
            ]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_output")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    def test_resolve_resource_attribute_module_reference(
        self, get_configuration_address_mock, clean_references_mock, resolve_module_output_mock
    ):
        value1 = Mock()
        value2 = Mock()
        resolve_module_output_mock.side_effect = [[value1], [value2]]
        clean_references_mock.return_value = ["module.layer1.arn", "module.layer2.arn"]
        get_configuration_address_mock.side_effect = ["layer1", "layer2"]

        layer1_module = TFModule(None, None, {}, [], {}, {"id": "layer1_id", "arn": "layer1.arn"})
        layer2_module = TFModule(None, None, {}, [], {}, {"id": "layer2_id", "arn": "layer2.arn"})
        other_module = TFModule(None, None, {}, [], {}, {})
        parent_module = TFModule(
            None,
            None,
            {},
            [],
            {
                "layer2": layer2_module,
                "layer1": layer1_module,
                "other": other_module,
            },
            {},
        )

        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=parent_module,
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["module.layer1.arn", "module.layer2.arn"]),
            },
        )
        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], value1)
        self.assertEqual(results[1], value2)

        get_configuration_address_mock.has_calls([call("layer1"), call("layer2")])

        resolve_module_output_mock.assert_has_calls(
            [
                call(
                    layer1_module,
                    "arn",
                ),
                call(
                    layer2_module,
                    "arn",
                ),
            ]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_resource_attribute_resource_reference(self, clean_references_mock):
        clean_references_mock.return_value = ["aws_lambda_layer.arn"]
        parent_module = TFModule(None, None, {}, [], {}, {})

        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=parent_module,
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["aws_lambda_layer.arn"]),
            },
        )
        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], ResolvedReference("aws_lambda_layer.arn", None))

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_variable")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_module_output")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._get_configuration_address")
    def test_resolve_resource_attribute_module_and_variable_references(
        self,
        get_configuration_address_mock,
        clean_references_mock,
        resolve_module_output_mock,
        resolve_module_variable_mock,
    ):
        variable_reference_value = Mock()
        resolve_module_variable_mock.return_value = [variable_reference_value]
        module_reference_value = Mock()
        resolve_module_output_mock.return_value = [module_reference_value]

        clean_references_mock.return_value = ["module.layer1.arn", "var.layer2_arn"]
        get_configuration_address_mock.side_effect = ["layer1", "layer2_arn"]

        layer1_module = TFModule(None, None, {}, [], {}, {"id": "layer1_id", "arn": "layer1.arn"})
        other_module = TFModule(None, None, {}, [], {}, {})
        parent_module = TFModule(
            None,
            None,
            {},
            [],
            {
                "layer1": layer1_module,
                "other": other_module,
            },
            {},
        )

        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=parent_module,
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["module.layer1.arn", "var.layer2_arn"]),
            },
        )
        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], module_reference_value)
        self.assertEqual(results[1], variable_reference_value)

        get_configuration_address_mock.has_calls([call("layer1"), call("layer2_arn")])

        resolve_module_output_mock.assert_has_calls(
            [
                call(
                    layer1_module,
                    "arn",
                ),
            ]
        )
        resolve_module_variable_mock.assert_has_calls(
            [
                call(
                    parent_module,
                    "layer2_arn",
                ),
            ]
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_resource_attribute_empty_child_module_for_module_output_case_exception_scenario(
        self, clean_references_mock
    ):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["module.layer1.arn"]),
            },
        )
        expected_exception_message = (
            "An error occurred when attempting to link two resources: The input resource "
            "aws_lambda_function.func does not have a parent module, or we could not find the "
            "child module layer1."
        )

        if resource.attributes.get("Layers"):
            clean_references_mock.return_value = resource.attributes["Layers"].value

        with self.assertRaises(InvalidResourceLinkingException) as exc:
            _resolve_resource_attribute(resource, "Layers")

        self.assertEqual(exc.exception.args[0], expected_exception_message)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_resource_attribute_no_child_module_for_module_output_case_exception_scenario(
        self, clean_references_mock
    ):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {"layer2": TFModule(None, None, {}, [], {}, {})}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=["module.layer1.arn"]),
            },
        )
        expected_exception_message = (
            "An error occurred when attempting to link two resources: The input resource "
            "aws_lambda_function.func does not have a parent module, or we could not find the "
            "child module layer1."
        )

        if resource.attributes.get("Layers"):
            clean_references_mock.return_value = resource.attributes["Layers"].value

        with self.assertRaises(InvalidResourceLinkingException) as exc:
            _resolve_resource_attribute(resource, "Layers")

        self.assertEqual(exc.exception.args[0], expected_exception_message)

    @parameterized.expand(["module.layer1", "module.layer1.arn.other", "module.", "module.."])
    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_resource_attribute_invalid_module_output_references_exception_scenario(
        self, module_output_reference, clean_references_mock
    ):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
                "Layers": References(value=[module_output_reference]),
            },
        )
        expected_exception_message = (
            "An error occurred when attempting to link two resources: The attribute Layers "
            f"in Resource aws_lambda_function.func has an invalid reference "
            f"{module_output_reference} value"
        )

        if resource.attributes.get("Layers"):
            clean_references_mock.return_value = resource.attributes["Layers"].value

        with self.assertRaises(InvalidResourceLinkingException) as exc:
            _resolve_resource_attribute(resource, "Layers")

        self.assertEqual(exc.exception.args[0], expected_exception_message)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._clean_references_list")
    def test_resolve_resource_attribute_no_value_use_case(self, clean_references_mock):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
            },
        )

        results = _resolve_resource_attribute(resource, "Layers")
        self.assertEqual(len(results), 0)


class TestResourceLinker(TestCase):
    def setUp(self) -> None:
        self.linker_exceptions = ResourcePairExceptions(
            multiple_resource_linking_exception=OneLambdaLayerLinkingLimitationException,
            local_variable_linking_exception=FunctionLayerLocalVariablesLinkingLimitationException,
        )
        self.sample_resource_linking_pair = ResourceLinkingPair(
            source_resource_cfn_resource=Mock(),
            source_resource_tf_config=Mock(),
            destination_resource_tf=Mock(),
            intrinsic_type=LinkerIntrinsics.Ref,
            cfn_intrinsic_attribute=None,
            source_link_field_name="Layers",
            terraform_link_field_name="layers",
            terraform_resource_type_prefix=LAMBDA_LAYER_RESOURCE_ADDRESS_PREFIX,
            linking_exceptions=self.linker_exceptions,
        )

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_resource_attribute")
    def test_handle_linking_valid_scenario(self, resolve_resource_attribute_mock):
        source_resources = Mock()
        dest_resources = [Mock()]
        resource = Mock()

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)

        resolved_dest_resources = Mock()
        resolve_resource_attribute_mock.return_value = resolved_dest_resources

        resource_linker._process_resolved_resources = Mock()
        resource_linker._process_resolved_resources.return_value = dest_resources

        resource_linker._update_mapped_parent_resource_with_resolved_child_resources = Mock()

        resource_linker._handle_linking(resource, source_resources)

        resource_linker._process_resolved_resources.assert_called_with(resource, resolved_dest_resources)
        resource_linker._update_mapped_parent_resource_with_resolved_child_resources.assert_called_with(
            source_resources, dest_resources
        )
        resolve_resource_attribute_mock.assert_called_with(resource, "layers")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking._resolve_resource_attribute")
    def test_handle_linking_multiple_destinations_exception(self, resolve_resource_attribute_mock):
        source_resources = Mock()
        dest_resources = ["layer2.arn", {"Ref": "layer1_logical_id"}]

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)

        resource_linker._process_resolved_resources = Mock()
        resource_linker._process_resolved_resources.return_value = dest_resources

        resource_linker._update_mapped_parent_resource_with_resolved_child_resources = Mock()

        resolved_destination_resources = [ResolvedReference("aws_lambda_layer_version.layer1.arn", "module.layer1")]
        resolve_resource_attribute_mock.return_value = resolved_destination_resources

        resource = Mock()
        resource.full_address = "func_full_address"
        expected_exception = (
            "AWS SAM CLI could not process a Terraform project that contains a source resource that is linked to more than "
            f"one destination resource. Destination resource(s) defined by {dest_resources} "
            f"could not be linked to source resource func_full_address."
            f"{os.linesep}Related issue: {ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK}."
        )
        with self.assertRaises(OneLambdaLayerLinkingLimitationException) as exc:
            resource_linker._handle_linking(resource, source_resources)
        self.assertEqual(exc.exception.args[0], expected_exception)

    def test_process_resolved_resources_constant_only(self):
        resource = Mock()

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._process_reference_resource_value = Mock()

        constant_value_resolved_resource = ConstantValue("layer1.arn")
        resolved_resources = [constant_value_resolved_resource]

        destination_resources = resource_linker._process_resolved_resources(resource, resolved_resources)

        self.assertEqual(destination_resources, [])
        resource_linker._process_reference_resource_value.assert_not_called()

    def test_process_resolved_resources_references_only(self):
        resource = Mock()

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._process_reference_resource_value = Mock()

        reference_resolved_layer = ResolvedReference("aws_lambda_layer_version.layer1.arn", "module.layer1")
        resolved_resources = [reference_resolved_layer]
        resource_linker._process_reference_resource_value = Mock()
        resource_linker._process_reference_resource_value.return_value = [{"Ref": "Layer1LogicalId"}]

        destination_resources = resource_linker._process_resolved_resources(resource, resolved_resources)

        self.assertEqual(destination_resources, [{"Ref": "Layer1LogicalId"}])
        resource_linker._process_reference_resource_value.assert_called_with(resource, reference_resolved_layer)

    def test_process_resolved_resources_mixed_constant_and_references(self):
        resource = Mock()
        resource.full_address = "func_full_address"

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._process_reference_resource_value = Mock()

        constant_value_resolved_resource = ConstantValue("layer1.arn")
        reference_resolved_resource = ResolvedReference("aws_lambda_layer_version.layer1.arn", "module.layer1")
        resolved_resources = [reference_resolved_resource, constant_value_resolved_resource]
        resource_linker._process_reference_resource_value.return_value = [{"Ref": "Layer1LogicalId"}]
        expected_exception = (
            "AWS SAM CLI could not process a Terraform project that contains a source resource that is linked to more than "
            f"one destination resource. Destination resource(s) defined by {resolved_resources} "
            f"could not be linked to source resource func_full_address."
            f"{os.linesep}Related issue: {ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK}."
        )
        with self.assertRaises(OneLambdaLayerLinkingLimitationException) as exc:
            resource_linker._process_resolved_resources(resource, resolved_resources)
        self.assertEqual(exc.exception.args[0], expected_exception)
        resource_linker._process_reference_resource_value.assert_called_with(resource, reference_resolved_resource)

    def test_process_resolved_resources_mixed_data_sources_and_references(self):
        resource = Mock()
        resource.full_address = "func_full_address"

        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._process_reference_resource_value = Mock()

        data_resources_resolved_resources = ResolvedReference("data.aws_region.current.name", "module.layer1")
        reference_resolved_resources = ResolvedReference("aws_lambda_layer_version.layer1.arn", "module.layer1")
        resolved_resources = [reference_resolved_resources, data_resources_resolved_resources]
        resource_linker._process_reference_resource_value.side_effect = [[{"Ref": "Layer1LogicalId"}], []]

        expected_exception = (
            "AWS SAM CLI could not process a Terraform project that contains a source resource "
            "that is linked to more than one destination resource. Destination resource(s) defined "
            f"by {resolved_resources} could not be linked to source resource func_full_address."
            f"{os.linesep}Related issue: {ONE_LAMBDA_LAYER_LINKING_ISSUE_LINK}."
        )
        with self.assertRaises(OneLambdaLayerLinkingLimitationException) as exc:
            resource_linker._process_resolved_resources(resource, resolved_resources)
        self.assertEqual(exc.exception.args[0], expected_exception)
        resource_linker._process_reference_resource_value.assert_has_calls(
            [
                call(resource, reference_resolved_resources),
                call(resource, data_resources_resolved_resources),
            ]
        )

    def test_process_reference_resource_value_data_resource_reference(self):
        reference_resolved_resource = ResolvedReference("data.aws_lambda_layer_version.layer1", "module.layer1")
        resource = Mock()
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        layers = resource_linker._process_reference_resource_value(resource, reference_resolved_resource)
        self.assertEqual(len(layers), 0)

    def test_process_reference_resource_value_reference_to_local_variables(self):
        reference_resolved_resources = ResolvedReference("local.layer_arn", "module.layer1")
        resource = Mock()
        resource.full_address = "func_full_address"
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        expected_exception = (
            "AWS SAM CLI could not process a Terraform project that uses local variables to define linked resources. "
            "Destination resource(s) defined by local.layer_arn could not be linked to destination resource "
            f"func_full_address.{os.linesep}Related issue: {LOCAL_VARIABLES_SUPPORT_ISSUE_LINK}."
        )
        with self.assertRaises(LocalVariablesLinkingLimitationException) as exc:
            resource_linker._process_reference_resource_value(resource, reference_resolved_resources)
        self.assertEqual(exc.exception.args[0], expected_exception)

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking.build_cfn_logical_id")
    def test_process_reference_resource_value_reference_to_an_existing_layer_resource(self, build_cfn_logical_id_mock):
        build_cfn_logical_id_mock.return_value = "layer1LogicalId"
        reference_resolved_layer = ResolvedReference("aws_lambda_layer_version.layer.arn", "module.layer1")
        resource = Mock()
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._resource_pair.destination_resource_tf = {"layer1LogicalId": Mock()}

        resources = resource_linker._process_reference_resource_value(resource, reference_resolved_layer)
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0], {"Ref": "layer1LogicalId"})
        build_cfn_logical_id_mock.assert_called_with("module.layer1.aws_lambda_layer_version.layer")

    @patch("samcli.hook_packages.terraform.hooks.prepare.resource_linking.build_cfn_logical_id")
    def test_process_reference_resource_value_reference_to_non_exist_layer_resource(self, build_cfn_logical_id_mock):
        build_cfn_logical_id_mock.return_value = "layer1LogicalId"
        reference_resolved_resources = ResolvedReference("aws_lambda_layer_version.layer.arn", None)
        resource = Mock()
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._resource_pair.destination_resource_tf = {"layer2LogicalId": Mock()}

        resources = resource_linker._process_reference_resource_value(resource, reference_resolved_resources)
        self.assertEqual(len(resources), 0)
        build_cfn_logical_id_mock.assert_called_with("aws_lambda_layer_version.layer")

    def test_process_reference_layer_value_reference_to_not_layer_resource_arn_property(self):
        reference_resolved_resource = ResolvedReference("aws_lambda_layer_version.layer.name", None)
        resource = Mock()
        resource.full_address = "func_full_address"
        expected_exception = (
            f"An error occurred when attempting to link two resources: Could not use the value "
            f"aws_lambda_layer_version.layer.name as a destination resource for the source "
            f"resource func_full_address. The source resource value should refer to valid destination "
            f"resource ARN property."
        )
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        with self.assertRaises(InvalidResourceLinkingException) as exc:
            resource_linker._process_reference_resource_value(resource, reference_resolved_resource)
        self.assertEqual(exc.exception.args[0], expected_exception)

    def test_process_reference_resource_value_reference_to_invalid_destination_resource(self):
        reference_resolved_resource = ResolvedReference("aws_lambda_layer_version2.layer.arn", None)
        resource = Mock()
        resource.full_address = "func_full_address"
        expected_exception = (
            f"An error occurred when attempting to link two resources: Could not use the value "
            f"aws_lambda_layer_version2.layer.arn as a destination for the source resource func_full_address. "
            f"The source resource value should refer to valid destination ARN property."
        )
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        with self.assertRaises(InvalidResourceLinkingException) as exc:
            resource_linker._process_reference_resource_value(resource, reference_resolved_resource)
        self.assertEqual(exc.exception.args[0], expected_exception)

    def test_update_mapped_lambda_function_with_resolved_layers(self):
        cfn_source_resources = [
            {"Type": "AWS::Lambda::Function", "Properties": {"Code": "/path/code1", "Runtime": "Python3.8"}},
            {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": "/path/code2", "Runtime": "Python3.8", "Layers": ["layer3.arn", "layer1.arn"]},
            },
        ]
        tf_destination_resources = {
            "layer1_logical_id": {
                "address": "aws_lambda_layer_version.layer1",
                "type": "aws_lambda_layer_version",
                "name": "layer1",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "values": {
                    "compatible_runtimes": ["python3.8"],
                    "filename": "/path/layer1_code",
                    "layer_name": "layer1",
                    "arn": "layer1.arn",
                },
            },
            "layer2_logical_id": {
                "address": "aws_lambda_layer_version.layer2",
                "type": "aws_lambda_layer_version",
                "name": "layer2",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "values": {
                    "compatible_runtimes": ["python3.8"],
                    "filename": "/path/layer2_code",
                    "layer_name": "layer2",
                },
            },
            "layer3_logical_id": {
                "address": "aws_lambda_layer_version.layer3",
                "type": "aws_lambda_layer_version",
                "name": "layer3",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "values": {
                    "compatible_runtimes": ["python3.8"],
                    "filename": "/path/layer2_code",
                    "layer_name": "layer3",
                },
            },
        }
        destination_resources = [{"Ref": "layer1_logical_id"}, {"Ref": "layer3_logical_id"}]
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._resource_pair.destination_resource_tf = tf_destination_resources
        resource_linker._update_mapped_parent_resource_with_resolved_child_resources(
            cfn_source_resources, destination_resources
        )
        self.assertEqual(cfn_source_resources[0]["Properties"]["Layers"], destination_resources)
        self.assertEqual(
            cfn_source_resources[1]["Properties"]["Layers"],
            ["layer3.arn", {"Ref": "layer1_logical_id"}, {"Ref": "layer3_logical_id"}],
        )

    def test_link_resources(self):
        source_config_resources = {
            "aws_lambda_function.remote_lambda_code": [
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "s3_remote_lambda_function",
                        "Code": {"S3Bucket": "lambda_code_bucket", "S3Key": "remote_lambda_code_key"},
                        "Handler": "app.lambda_handler",
                        "PackageType": "Zip",
                        "Runtime": "python3.8",
                        "Timeout": 3,
                    },
                    "Metadata": {"SamResourceId": "aws_lambda_function.remote_lambda_code", "SkipBuild": True},
                }
            ],
            "aws_lambda_function.root_lambda": [
                {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "root_lambda",
                        "Code": "HelloWorldFunction.zip",
                        "Handler": "app.lambda_handler",
                        "PackageType": "Zip",
                        "Runtime": "python3.8",
                        "Timeout": 3,
                    },
                    "Metadata": {"SamResourceId": "aws_lambda_function.root_lambda", "SkipBuild": True},
                }
            ],
        }
        resources = {
            "aws_lambda_function.remote_lambda_code": TFResource(
                "aws_lambda_function.remote_lambda_code", "", None, {}
            ),
            "aws_lambda_function.root_lambda": TFResource("aws_lambda_function.root_lambda", "", None, {}),
        }
        resource_linker = ResourceLinker(self.sample_resource_linking_pair)
        resource_linker._resource_pair.source_resource_cfn_resource = source_config_resources
        resource_linker._resource_pair.source_resource_tf_config = resources
        resource_linker._handle_linking = Mock()

        resource_linker.link_resources()

        resource_linker._handle_linking.assert_has_calls(
            [
                call(
                    resources["aws_lambda_function.remote_lambda_code"],
                    source_config_resources.get("aws_lambda_function.remote_lambda_code"),
                ),
                call(
                    resources["aws_lambda_function.root_lambda"],
                    source_config_resources.get("aws_lambda_function.root_lambda"),
                ),
            ]
        )
