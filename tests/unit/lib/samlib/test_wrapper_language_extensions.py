"""
Tests for language extensions detection functions (canonical implementations in sam_integration)
and SamTranslatorWrapper's get_dynamic_artifact_properties / _check_using_language_extension.

After the Phase 1/Phase 2 separation, the canonical implementations of
detect_dynamic_artifact_properties, detect_foreach_dynamic_properties,
resolve_collection, resolve_parameter_collection, and contains_loop_variable
live in samcli.lib.cfn_language_extensions.sam_integration. The delegation
wrappers on SamTranslatorWrapper have been removed as dead code.
"""

from unittest import TestCase
from unittest.mock import patch

from samcli.lib.cfn_language_extensions.sam_integration import (
    check_using_language_extension,
    contains_loop_variable,
    detect_dynamic_artifact_properties,
    detect_foreach_dynamic_properties,
    resolve_collection,
    resolve_parameter_collection,
)
from samcli.lib.samlib.wrapper import SamTranslatorWrapper


class TestDetectDynamicArtifactProperties(TestCase):
    """Tests for detect_dynamic_artifact_properties."""

    def test_empty_resources(self):
        result = detect_dynamic_artifact_properties({"Resources": {}})
        self.assertEqual(result, [])

    def test_no_resources_key(self):
        result = detect_dynamic_artifact_properties({})
        self.assertEqual(result, [])

    def test_non_dict_resources(self):
        result = detect_dynamic_artifact_properties({"Resources": "invalid"})
        self.assertEqual(result, [])

    def test_regular_resources_no_foreach(self):
        template = {
            "Resources": {
                "MyFunc": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src"},
                }
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(result, [])

    def test_foreach_with_dynamic_codeuri(self):
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./services/${Name}"},
                        }
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].foreach_key, "Fn::ForEach::Services")
        self.assertEqual(result[0].loop_name, "Services")
        self.assertEqual(result[0].loop_variable, "Name")
        self.assertEqual(result[0].collection, ["Users", "Orders"])
        self.assertEqual(result[0].resource_key, "${Name}Function")
        self.assertEqual(result[0].property_name, "CodeUri")
        self.assertEqual(result[0].property_value, "./services/${Name}")

    def test_foreach_with_static_codeuri_no_loop_var(self):
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./shared-src"},
                        }
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(result, [])

    def test_foreach_with_non_packageable_resource(self):
        template = {
            "Resources": {
                "Fn::ForEach::Topics": [
                    "Name",
                    ["A", "B"],
                    {
                        "${Name}Topic": {
                            "Type": "AWS::SNS::Topic",
                            "Properties": {"TopicName": "${Name}"},
                        }
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(result, [])

    def test_multiple_foreach_blocks(self):
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FuncName",
                    ["Alpha", "Beta"],
                    {
                        "${FuncName}Func": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./${FuncName}"},
                        }
                    },
                ],
                "Fn::ForEach::Layers": [
                    "LayerName",
                    ["Common", "Utils"],
                    {
                        "${LayerName}Layer": {
                            "Type": "AWS::Serverless::LayerVersion",
                            "Properties": {"ContentUri": "./layers/${LayerName}"},
                        }
                    },
                ],
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(result), 2)
        names = {r.property_name for r in result}
        self.assertEqual(names, {"CodeUri", "ContentUri"})


class TestDetectForeachDynamicProperties(TestCase):
    """Tests for detect_foreach_dynamic_properties."""

    def test_invalid_foreach_not_list(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", "not a list", {})
        self.assertEqual(result, [])

    def test_invalid_foreach_wrong_length(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["only", "two"], {})
        self.assertEqual(result, [])

    def test_non_string_loop_variable(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", [123, ["A"], {}], {})
        self.assertEqual(result, [])

    def test_non_dict_output_template(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"], "not a dict"], {})
        self.assertEqual(result, [])

    def test_non_dict_resource_def_skipped(self):
        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"], {"${Name}Func": "not a dict"}], {})
        self.assertEqual(result, [])

    def test_non_string_resource_type_skipped(self):
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            ["Name", ["A"], {"${Name}Func": {"Type": 123, "Properties": {}}}],
            {},
        )
        self.assertEqual(result, [])

    def test_non_dict_properties_skipped(self):
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            ["Name", ["A"], {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": "bad"}}],
            {},
        )
        self.assertEqual(result, [])

    def test_empty_collection_returns_empty(self):
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            [
                "Name",
                {"Ref": "NonExistentParam"},
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./${Name}"}}},
            ],
            {},
        )
        self.assertEqual(result, [])

    def test_property_value_none_skipped(self):
        """If a packageable property is not present (None), it should be skipped."""
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            [
                "Name",
                ["A"],
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"Handler": "main.handler"}}},
            ],
            {},
        )
        self.assertEqual(result, [])

    def test_parameter_ref_collection(self):
        template = {
            "Parameters": {"FuncNames": {"Type": "CommaDelimitedList", "Default": "Alpha,Beta,Gamma"}},
            "Resources": {},
        }
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::Funcs",
            [
                "Name",
                {"Ref": "FuncNames"},
                {
                    "${Name}Func": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "./${Name}"},
                    }
                },
            ],
            template,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].collection, ["Alpha", "Beta", "Gamma"])


class TestResolveCollection(TestCase):
    """Tests for resolve_collection."""

    def test_static_list(self):
        result = resolve_collection(["A", "B", "C"], {})
        self.assertEqual(result, ["A", "B", "C"])

    def test_static_list_with_none_items(self):
        result = resolve_collection(["A", None, "C"], {})
        self.assertEqual(result, ["A", "C"])

    def test_static_list_with_numeric_items(self):
        result = resolve_collection([1, 2, 3], {})
        self.assertEqual(result, ["1", "2", "3"])

    def test_ref_parameter(self):
        template = {
            "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "X,Y"}},
        }
        result = resolve_collection({"Ref": "Names"}, template)
        self.assertEqual(result, ["X", "Y"])

    def test_unsupported_intrinsic(self):
        result = resolve_collection({"Fn::Split": [",", "a,b"]}, {})
        self.assertEqual(result, [])

    def test_string_value_returns_empty(self):
        result = resolve_collection("not a list or dict", {})
        self.assertEqual(result, [])

    def test_integer_value_returns_empty(self):
        result = resolve_collection(42, {})
        self.assertEqual(result, [])


class TestResolveParameterCollection(TestCase):
    """Tests for resolve_parameter_collection."""

    def test_from_parameter_overrides_list(self):
        result = resolve_parameter_collection("Names", {}, parameter_values={"Names": ["A", "B"]})
        self.assertEqual(result, ["A", "B"])

    def test_from_parameter_overrides_comma_string(self):
        result = resolve_parameter_collection("Names", {}, parameter_values={"Names": "Alpha, Beta, Gamma"})
        self.assertEqual(result, ["Alpha", "Beta", "Gamma"])

    def test_from_template_default_list(self):
        template = {
            "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": ["X", "Y"]}},
        }
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, ["X", "Y"])

    def test_from_template_default_comma_string(self):
        template = {
            "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "Foo,Bar"}},
        }
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, ["Foo", "Bar"])

    def test_parameter_not_found(self):
        result = resolve_parameter_collection("Missing", {})
        self.assertEqual(result, [])

    def test_parameter_overrides_take_precedence(self):
        template = {
            "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "Default1,Default2"}},
        }
        result = resolve_parameter_collection("Names", template, parameter_values={"Names": "Override1,Override2"})
        self.assertEqual(result, ["Override1", "Override2"])

    def test_non_dict_param_def_returns_empty(self):
        template = {"Parameters": {"Names": "not a dict"}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, [])

    def test_no_default_in_param_def_returns_empty(self):
        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList"}}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, [])

    def test_no_parameters_section(self):
        result = resolve_parameter_collection("Names", {"Resources": {}})
        self.assertEqual(result, [])


class TestContainsLoopVariable(TestCase):
    """Tests for contains_loop_variable."""

    def test_string_with_variable(self):
        self.assertTrue(contains_loop_variable("./src/${Name}", "Name"))

    def test_string_without_variable(self):
        self.assertFalse(contains_loop_variable("./src/static", "Name"))

    def test_string_partial_match_not_detected(self):
        self.assertFalse(contains_loop_variable("./src/${NameExtra}", "Name"))

    def test_dict_with_fn_sub_string(self):
        value = {"Fn::Sub": "./services/${Name}/code"}
        self.assertTrue(contains_loop_variable(value, "Name"))

    def test_dict_with_fn_sub_list(self):
        value = {"Fn::Sub": ["./services/${Name}/code", {"Name": "test"}]}
        self.assertTrue(contains_loop_variable(value, "Name"))

    def test_dict_with_fn_sub_no_match(self):
        value = {"Fn::Sub": "./services/static/code"}
        self.assertFalse(contains_loop_variable(value, "Name"))

    def test_nested_dict(self):
        value = {"Fn::Join": ["/", ["prefix", "${Name}"]]}
        self.assertTrue(contains_loop_variable(value, "Name"))

    def test_list_with_variable(self):
        value = ["static", "${Name}", "more"]
        self.assertTrue(contains_loop_variable(value, "Name"))

    def test_list_without_variable(self):
        value = ["static", "no-var", "more"]
        self.assertFalse(contains_loop_variable(value, "Name"))

    def test_integer_value(self):
        self.assertFalse(contains_loop_variable(42, "Name"))

    def test_none_value(self):
        self.assertFalse(contains_loop_variable(None, "Name"))

    def test_bool_value(self):
        self.assertFalse(contains_loop_variable(True, "Name"))

    def test_fn_sub_list_empty(self):
        value = {"Fn::Sub": []}
        self.assertFalse(contains_loop_variable(value, "Name"))


class TestGetDynamicArtifactProperties(TestCase):
    """Tests for SamTranslatorWrapper.get_dynamic_artifact_properties."""

    def test_returns_detected_properties_via_language_extension_result(self):
        """When language_extension_result is provided, dynamic properties come from it."""
        from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_props = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Funcs",
                loop_name="Funcs",
                loop_variable="Name",
                collection=["A", "B"],
                resource_key="${Name}Func",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./${Name}",
            )
        ]
        result = LanguageExtensionResult(
            expanded_template={"Resources": {}},
            original_template={"Resources": {}},
            dynamic_artifact_properties=dynamic_props,
            had_language_extensions=True,
        )
        with patch("samcli.lib.samlib.wrapper.SamTemplateValidator"):
            wrapper = SamTranslatorWrapper({"Resources": {}}, language_extension_result=result)
        props = wrapper.get_dynamic_artifact_properties()
        self.assertEqual(len(props), 1)
        self.assertEqual(props[0].loop_name, "Funcs")

    def test_returns_empty_when_no_foreach(self):
        template = {"Resources": {"MyFunc": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./src"}}}}
        with patch("samcli.lib.samlib.wrapper.SamTemplateValidator"):
            wrapper = SamTranslatorWrapper(template)
        props = wrapper.get_dynamic_artifact_properties()
        self.assertEqual(props, [])


class TestCheckUsingLanguageExtension(TestCase):
    """Additional edge case tests for _check_using_language_extension."""

    def test_none_template(self):
        self.assertFalse(check_using_language_extension(None))

    def test_no_transform_key(self):
        self.assertFalse(check_using_language_extension({"Resources": {}}))

    def test_empty_transform(self):
        self.assertFalse(check_using_language_extension({"Transform": ""}))

    def test_list_with_non_string_entries(self):
        self.assertFalse(check_using_language_extension({"Transform": [{"Name": "AWS::Include"}, 42]}))

    def test_list_with_language_extensions(self):
        self.assertTrue(
            check_using_language_extension({"Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]})
        )
