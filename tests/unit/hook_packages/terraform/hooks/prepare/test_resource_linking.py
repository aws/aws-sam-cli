from copy import deepcopy
from unittest import TestCase
from unittest.mock import Mock, patch, call

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
    _resolve_module_variable,
    _build_module,
    _build_expression_from_configuration,
    _build_module_full_address,
    _build_child_modules_from_configuration,
    _build_module_outputs_from_configuration,
    _build_module_resources_from_configuration,
    _build_module_variables_from_configuration,
    _resolve_resource_attribute,
    ResolvedReference,
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
                TFModule("module.name", None, {}, [], {}, {"mycooloutput": References(["local.mycoolconst"])}),
                "module.name",
            ),
            (TFModule(None, None, {}, [], {}, {"mycooloutput": References(["local.mycoolconst"])}), None),
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

        expected_resources = [
            TFResource(
                "resource1_address",
                "resource1_type",
                mock_module,
                {"expression1": mock_parsed_expression, "expression2": mock_parsed_expression},
            ),
            TFResource(
                "resource2_address",
                "resource2_type",
                mock_module,
                {"expression3": mock_parsed_expression, "expression4": mock_parsed_expression},
            ),
        ]

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
    def test_resolve_resource_attribute_none_value_exception_scenario(self, clean_references_mock):
        resource = TFResource(
            address="aws_lambda_function.func",
            type="aws_lambda_function",
            module=TFModule(None, None, {}, [], {}, {}),
            attributes={
                "Code": ConstantValue(value="/path/code"),
            },
        )
        expected_exception_message = (
            "An error occurred when attempting to link two resources: The attribute Layers "
            "could not be found in resource aws_lambda_function.func."
        )

        with self.assertRaises(InvalidResourceLinkingException) as exc:
            _resolve_resource_attribute(resource, "Layers")

        self.assertEqual(exc.exception.args[0], expected_exception_message)
