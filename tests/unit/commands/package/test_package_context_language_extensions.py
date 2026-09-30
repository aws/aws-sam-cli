"""
Tests for language extensions packaging support.

Covers _copy_artifact_uris_for_type with various resource types and dynamic property skipping.
These functions now live in samcli.lib.package.language_extensions_packaging.
"""

from unittest import TestCase
from unittest.mock import patch, MagicMock

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.package.language_extensions_packaging import (
    _compute_mapping_name,
    _copy_artifact_uris_for_type,
    _nesting_path,
    _prop_identity,
    _update_foreach_with_s3_uris,
    _generate_artifact_mappings,
    _apply_artifact_mappings_to_template,
    _replace_dynamic_artifact_with_findmap,
)


class TestCopyArtifactUrisForType(TestCase):
    """Tests for _copy_artifact_uris_for_type."""

    def test_serverless_function_codeuri(self):
        original = {}
        exported = {"CodeUri": "s3://bucket/code.zip"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::Function")
        self.assertTrue(result)
        self.assertEqual(original["CodeUri"], "s3://bucket/code.zip")

    def test_serverless_function_imageuri(self):
        original = {}
        exported = {"ImageUri": "123456.dkr.ecr.us-east-1.amazonaws.com/repo:tag"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::Function")
        self.assertTrue(result)
        self.assertEqual(original["ImageUri"], "123456.dkr.ecr.us-east-1.amazonaws.com/repo:tag")

    def test_lambda_function_code(self):
        original = {}
        exported = {"Code": {"S3Bucket": "bucket", "S3Key": "key"}}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Lambda::Function")
        self.assertTrue(result)
        self.assertEqual(original["Code"]["S3Bucket"], "bucket")

    def test_serverless_layer_contenturi(self):
        original = {}
        exported = {"ContentUri": "s3://bucket/layer.zip"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::LayerVersion")
        self.assertTrue(result)
        self.assertEqual(original["ContentUri"], "s3://bucket/layer.zip")

    def test_lambda_layer_content(self):
        original = {}
        exported = {"Content": {"S3Bucket": "bucket", "S3Key": "key"}}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Lambda::LayerVersion")
        self.assertTrue(result)

    def test_serverless_api_definitionuri(self):
        original = {}
        exported = {"DefinitionUri": "s3://bucket/api.yaml"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::Api")
        self.assertTrue(result)
        self.assertEqual(original["DefinitionUri"], "s3://bucket/api.yaml")

    def test_serverless_httpapi_definitionuri(self):
        original = {}
        exported = {"DefinitionUri": "s3://bucket/httpapi.yaml"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::HttpApi")
        self.assertTrue(result)

    def test_serverless_statemachine_definitionuri(self):
        original = {}
        exported = {"DefinitionUri": "s3://bucket/sm.json"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::StateMachine")
        self.assertTrue(result)

    def test_serverless_graphqlapi_schemauri(self):
        original = {}
        exported = {"SchemaUri": "s3://bucket/schema.graphql"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::GraphQLApi")
        self.assertTrue(result)
        self.assertEqual(original["SchemaUri"], "s3://bucket/schema.graphql")

    def test_serverless_graphqlapi_codeuri(self):
        original = {}
        exported = {"CodeUri": "s3://bucket/resolvers.zip"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::GraphQLApi")
        self.assertTrue(result)

    def test_apigateway_restapi_bodys3location(self):
        original = {}
        exported = {"BodyS3Location": "s3://bucket/body.yaml"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::ApiGateway::RestApi")
        self.assertTrue(result)

    def test_apigatewayv2_api_bodys3location(self):
        original = {}
        exported = {"BodyS3Location": "s3://bucket/body.yaml"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::ApiGatewayV2::Api")
        self.assertTrue(result)

    def test_stepfunctions_statemachine_definitions3location(self):
        original = {}
        exported = {"DefinitionS3Location": "s3://bucket/sm.json"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::StepFunctions::StateMachine")
        self.assertTrue(result)

    def test_unknown_resource_type_returns_false(self):
        original = {}
        exported = {"SomeUri": "s3://bucket/thing"}
        result = _copy_artifact_uris_for_type(original, exported, "AWS::SNS::Topic")
        self.assertFalse(result)

    def test_no_matching_property_returns_false(self):
        original = {}
        exported = {"Handler": "index.handler"}  # Not an artifact property
        result = _copy_artifact_uris_for_type(original, exported, "AWS::Serverless::Function")
        self.assertFalse(result)

    def test_dynamic_property_skipped(self):
        original = {}
        exported = {"CodeUri": "s3://bucket/code.zip"}
        dynamic_keys = {("Fn::ForEach::Funcs", "CodeUri")}
        result = _copy_artifact_uris_for_type(
            original,
            exported,
            "AWS::Serverless::Function",
            foreach_key="Fn::ForEach::Funcs",
            dynamic_prop_keys=dynamic_keys,
        )
        self.assertFalse(result)
        self.assertNotIn("CodeUri", original)

    def test_non_dynamic_property_not_skipped(self):
        original = {}
        exported = {"CodeUri": "s3://bucket/code.zip"}
        dynamic_keys = {("Fn::ForEach::Other", "CodeUri")}
        result = _copy_artifact_uris_for_type(
            original,
            exported,
            "AWS::Serverless::Function",
            foreach_key="Fn::ForEach::Funcs",
            dynamic_prop_keys=dynamic_keys,
        )
        self.assertTrue(result)
        self.assertEqual(original["CodeUri"], "s3://bucket/code.zip")

    def test_no_foreach_key_skips_dynamic_check(self):
        original = {}
        exported = {"CodeUri": "s3://bucket/code.zip"}
        dynamic_keys = {("Fn::ForEach::Funcs", "CodeUri")}
        result = _copy_artifact_uris_for_type(
            original,
            exported,
            "AWS::Serverless::Function",
            foreach_key=None,
            dynamic_prop_keys=dynamic_keys,
        )
        self.assertTrue(result)


class TestDetectForeachDynamicProperties(TestCase):
    """Tests for detect_foreach_dynamic_properties in sam_integration module."""

    def test_non_string_loop_variable(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties("Fn::ForEach::X", [123, ["A"], {}], {})
        self.assertEqual(result, [])

    def test_non_dict_output_template(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"], "not a dict"], {})
        self.assertEqual(result, [])

    def test_non_dict_resource_def_skipped(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties("Fn::ForEach::X", ["Name", ["A"], {"${Name}Func": "not a dict"}], {})
        self.assertEqual(result, [])

    def test_non_string_resource_type_skipped(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            ["Name", ["A"], {"${Name}Func": {"Type": 123, "Properties": {}}}],
            {},
        )
        self.assertEqual(result, [])

    def test_non_packageable_resource_skipped(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            ["Name", ["A"], {"${Name}Topic": {"Type": "AWS::SNS::Topic", "Properties": {}}}],
            {},
        )
        self.assertEqual(result, [])

    def test_non_dict_properties_skipped(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            ["Name", ["A"], {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": "bad"}}],
            {},
        )
        self.assertEqual(result, [])

    def test_parameter_ref_collection_detected(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        template = {
            "Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "A,B"}},
        }
        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::Funcs",
            [
                "Name",
                {"Ref": "Names"},
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./${Name}"}}},
            ],
            template,
        )
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].collection_is_parameter_ref)
        self.assertEqual(result[0].collection_parameter_name, "Names")

    def test_static_collection_not_parameter_ref(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::Funcs",
            [
                "Name",
                ["A", "B"],
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./${Name}"}}},
            ],
            {},
        )
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0].collection_is_parameter_ref)

    def test_empty_collection_returns_empty(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_foreach_dynamic_properties

        result = detect_foreach_dynamic_properties(
            "Fn::ForEach::X",
            [
                "Name",
                {"Ref": "Missing"},
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./${Name}"}}},
            ],
            {},
        )
        self.assertEqual(result, [])


class TestResolveCollection(TestCase):
    """Tests for resolve_collection in sam_integration module."""

    def test_static_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        result = resolve_collection(["A", "B", "C"], {})
        self.assertEqual(result, ["A", "B", "C"])

    def test_static_list_with_none(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        result = resolve_collection(["A", None, "C"], {})
        self.assertEqual(result, ["A", "C"])

    def test_ref_parameter(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "X,Y"}}}
        result = resolve_collection({"Ref": "Names"}, template)
        self.assertEqual(result, ["X", "Y"])

    def test_unsupported_returns_empty(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        result = resolve_collection("string", {})
        self.assertEqual(result, [])

    def test_non_ref_dict_returns_empty(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        result = resolve_collection({"Fn::Split": [",", "a,b"]}, {})
        self.assertEqual(result, [])


class TestResolveParameterCollection(TestCase):
    """Tests for resolve_parameter_collection in sam_integration module."""

    def test_from_overrides_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        result = resolve_parameter_collection("Names", {}, parameter_values={"Names": ["A", "B"]})
        self.assertEqual(result, ["A", "B"])

    def test_from_overrides_comma_string(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        result = resolve_parameter_collection("Names", {}, parameter_values={"Names": "X, Y, Z"})
        self.assertEqual(result, ["X", "Y", "Z"])

    def test_from_template_default_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": ["P", "Q"]}}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, ["P", "Q"])

    def test_from_template_default_string(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "M,N"}}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, ["M", "N"])

    def test_not_found_returns_empty(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        result = resolve_parameter_collection("Missing", {})
        self.assertEqual(result, [])

    def test_non_dict_param_def(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        template = {"Parameters": {"Names": "not a dict"}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, [])

    def test_no_default_returns_empty(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList"}}}
        result = resolve_parameter_collection("Names", template)
        self.assertEqual(result, [])

    def test_overrides_take_precedence(self):
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_parameter_collection

        template = {"Parameters": {"Names": {"Type": "CommaDelimitedList", "Default": "Default1,Default2"}}}
        result = resolve_parameter_collection("Names", template, parameter_values={"Names": "Override1,Override2"})
        self.assertEqual(result, ["Override1", "Override2"])


class TestReplaceDynamicArtifactEdgeCases(TestCase):
    """Tests for _replace_dynamic_artifact_with_findmap edge cases."""

    def test_body_not_dict_returns_false(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Funcs",
            loop_name="Funcs",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )
        resources = {
            "Fn::ForEach::Funcs": ["Name", ["A", "B"], "not a dict"],
        }
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)

    def test_properties_not_dict_returns_false(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Funcs",
            loop_name="Funcs",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )
        resources = {
            "Fn::ForEach::Funcs": [
                "Name",
                ["A", "B"],
                {"${Name}Func": {"Type": "AWS::Serverless::Function", "Properties": "not a dict"}},
            ],
        }
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)

    def test_resource_key_not_found_returns_false(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Funcs",
            loop_name="Funcs",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )
        resources = {
            "Fn::ForEach::Funcs": [
                "Name",
                ["A", "B"],
                {"${Name}Other": {"Type": "AWS::Serverless::Function", "Properties": {"CodeUri": "./${Name}"}}},
            ],
        }
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)


class TestContainsLoopVariablePackageContext(TestCase):
    """Tests for contains_loop_variable in sam_integration module."""

    def test_ref_dict_matches(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertTrue(contains_loop_variable({"Ref": "Name"}, "Name"))

    def test_ref_dict_no_match(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertFalse(contains_loop_variable({"Ref": "Other"}, "Name"))

    def test_fn_sub_string(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertTrue(contains_loop_variable({"Fn::Sub": "./${Name}/code"}, "Name"))

    def test_fn_sub_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertTrue(contains_loop_variable({"Fn::Sub": ["./${Name}/code", {}]}, "Name"))

    def test_fn_sub_empty_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertFalse(contains_loop_variable({"Fn::Sub": []}, "Name"))

    def test_nested_dict(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertTrue(contains_loop_variable({"Fn::Join": ["/", ["${Name}"]]}, "Name"))

    def test_list_with_variable(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertTrue(contains_loop_variable(["${Name}", "other"], "Name"))

    def test_non_string_non_dict_non_list(self):
        from samcli.lib.cfn_language_extensions.sam_integration import contains_loop_variable

        self.assertFalse(contains_loop_variable(42, "Name"))


class TestNestedForEachRecursiveDetection(TestCase):
    """Tests for recursive detection of dynamic artifact properties in nested Fn::ForEach."""

    def test_nested_foreach_inner_dynamic_detected(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                "Fn::ForEach::Envs": [
                    "Env",
                    ["dev", "prod"],
                    {
                        "Fn::ForEach::Services": [
                            "Svc",
                            ["Users", "Orders"],
                            {
                                "${Env}${Svc}Function": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {"CodeUri": "./services/${Svc}", "Handler": "index.handler"},
                                }
                            },
                        ]
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].loop_variable, "Svc")
        self.assertEqual(result[0].loop_name, "Services")
        self.assertEqual(result[0].collection, ["Users", "Orders"])
        self.assertEqual(result[0].foreach_key, "Fn::ForEach::Services")
        # outer_loops should contain the enclosing Envs loop
        self.assertEqual(len(result[0].outer_loops), 1)
        self.assertEqual(result[0].outer_loops[0][0], "Fn::ForEach::Envs")
        self.assertEqual(result[0].outer_loops[0][1], "Env")
        self.assertEqual(result[0].outer_loops[0][2], ["dev", "prod"])

    def test_non_nested_foreach_still_works(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Svc",
                    ["Users", "Orders"],
                    {
                        "${Svc}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./services/${Svc}"},
                        }
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].outer_loops, [])

    def test_nested_foreach_static_not_detected(self):
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                "Fn::ForEach::Envs": [
                    "Env",
                    ["dev", "prod"],
                    {
                        "Fn::ForEach::Services": [
                            "Svc",
                            ["Users", "Orders"],
                            {
                                "${Env}${Svc}Function": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {"CodeUri": "./src", "Handler": "index.handler"},
                                }
                            },
                        ]
                    },
                ]
            }
        }
        result = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(result), 0)


class TestNestedForEachPackageS3UriUpdate(TestCase):
    """Tests for recursive _update_foreach_with_s3_uris."""

    def test_nested_foreach_recurses_into_inner_block(self):
        foreach_value = [
            "Env",
            ["dev", "prod"],
            {
                "Fn::ForEach::Services": [
                    "Svc",
                    ["Users", "Orders"],
                    {
                        "${Env}${Svc}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./src"},
                        }
                    },
                ]
            },
        ]
        exported_resources = {
            "devUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/abc.zip"},
            },
            "devOrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/abc.zip"},
            },
        }
        # Should not raise — recursion should handle the nested block
        _update_foreach_with_s3_uris("Fn::ForEach::Envs", foreach_value, exported_resources)
        # The inner static CodeUri should be updated
        inner_body = foreach_value[2]["Fn::ForEach::Services"][2]
        inner_props = inner_body["${Env}${Svc}Function"]["Properties"]
        self.assertEqual(inner_props["CodeUri"], "s3://bucket/abc.zip")

    def test_nested_foreach_skips_dynamic_properties(self):
        foreach_value = [
            "Env",
            ["dev", "prod"],
            {
                "Fn::ForEach::Services": [
                    "Svc",
                    ["Users", "Orders"],
                    {
                        "${Env}${Svc}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./services/${Svc}"},
                        }
                    },
                ]
            },
        ]
        exported_resources = {
            "devUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
        }
        dynamic_prop_keys = {("Fn::ForEach::Services", "CodeUri")}
        _update_foreach_with_s3_uris("Fn::ForEach::Envs", foreach_value, exported_resources, dynamic_prop_keys)
        # Dynamic property should NOT be updated (handled by Mappings)
        inner_body = foreach_value[2]["Fn::ForEach::Services"][2]
        inner_props = inner_body["${Env}${Svc}Function"]["Properties"]
        self.assertEqual(inner_props["CodeUri"], "./services/${Svc}")


class TestNestedForEachGenerateArtifactMappings(TestCase):
    """Tests for _generate_artifact_mappings with nested ForEach (compound vs simple keys)."""

    def test_inner_only_variable_produces_simple_keys(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Env}${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Svc}",
            outer_loops=[("Fn::ForEach::Envs", "Env", ["dev", "prod"])],
        )
        exported_resources = {
            "devUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "devOrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
            "prodUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "prodOrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
        }
        mappings, prop_to_mapping = _generate_artifact_mappings([prop], "/tmp", exported_resources)
        self.assertIn("SAMCodeUriEnvsServices", mappings)
        # Simple keys — inner collection values only
        self.assertIn("Users", mappings["SAMCodeUriEnvsServices"])
        self.assertIn("Orders", mappings["SAMCodeUriEnvsServices"])
        self.assertEqual(mappings["SAMCodeUriEnvsServices"]["Users"]["CodeUri"], "s3://bucket/users.zip")

    def test_compound_keys_when_outer_variable_referenced(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Env}${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Env}/${Svc}",  # References BOTH variables
            outer_loops=[("Fn::ForEach::Envs", "Env", ["dev", "prod"])],
        )
        exported_resources = {
            "devUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/dev-users.zip"},
            },
            "devOrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/dev-orders.zip"},
            },
            "prodUsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/prod-users.zip"},
            },
            "prodOrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/prod-orders.zip"},
            },
        }
        mappings, _ = _generate_artifact_mappings([prop], "/tmp", exported_resources)
        self.assertIn("SAMCodeUriEnvsServices", mappings)
        # Compound keys
        self.assertIn("dev-Users", mappings["SAMCodeUriEnvsServices"])
        self.assertIn("dev-Orders", mappings["SAMCodeUriEnvsServices"])
        self.assertIn("prod-Users", mappings["SAMCodeUriEnvsServices"])
        self.assertIn("prod-Orders", mappings["SAMCodeUriEnvsServices"])
        self.assertEqual(mappings["SAMCodeUriEnvsServices"]["dev-Users"]["CodeUri"], "s3://bucket/dev-users.zip")

    def test_non_nested_behavior_unchanged(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Svc}",
            outer_loops=[],  # No outer loops
        )
        exported_resources = {
            "UsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "OrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
        }
        mappings, _ = _generate_artifact_mappings([prop], "/tmp", exported_resources)
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertIn("Users", mappings["SAMCodeUriServices"])
        self.assertIn("Orders", mappings["SAMCodeUriServices"])
        # No compound keys
        self.assertNotIn("dev-Users", mappings["SAMCodeUriServices"])


class TestNestedForEachReplaceWithFindInMap(TestCase):
    """Tests for _replace_dynamic_artifact_with_findmap with nested ForEach."""

    def test_nested_foreach_traverses_outer_loops(self):
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Envs": [
                "Env",
                ["dev", "prod"],
                {
                    "Fn::ForEach::Services": [
                        "Svc",
                        ["Users", "Orders"],
                        {
                            "${Env}${Svc}Function": {
                                "Type": "AWS::Serverless::Function",
                                "Properties": {"CodeUri": "./services/${Svc}"},
                            }
                        },
                    ]
                },
            ]
        }
        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Env}${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Svc}",
            outer_loops=[("Fn::ForEach::Envs", "Env", ["dev", "prod"])],
        )
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertTrue(result)
        # Verify the inner property was replaced
        inner_body = resources["Fn::ForEach::Envs"][2]["Fn::ForEach::Services"][2]
        inner_props = inner_body["${Env}${Svc}Function"]["Properties"]
        self.assertIn("Fn::FindInMap", inner_props["CodeUri"])
        self.assertEqual(inner_props["CodeUri"]["Fn::FindInMap"][0], "SAMCodeUriEnvsServices")
        # Property references only inner var, so lookup should be simple Ref
        self.assertEqual(inner_props["CodeUri"]["Fn::FindInMap"][1], {"Ref": "Svc"})

    def test_nested_foreach_compound_key_uses_fn_join(self):
        """Test that when property references both outer and inner vars, Fn::Join is used."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Envs": [
                "Env",
                ["dev", "prod"],
                {
                    "Fn::ForEach::Services": [
                        "Svc",
                        ["api", "worker"],
                        {
                            "${Env}${Svc}Function": {
                                "Type": "AWS::Serverless::Function",
                                "Properties": {"CodeUri": "./services/${Env}/${Svc}"},
                            }
                        },
                    ]
                },
            ]
        }
        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["api", "worker"],
            resource_key="${Env}${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Env}/${Svc}",
            outer_loops=[("Fn::ForEach::Envs", "Env", ["dev", "prod"])],
        )
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertTrue(result)

        inner_body = resources["Fn::ForEach::Envs"][2]["Fn::ForEach::Services"][2]
        inner_props = inner_body["${Env}${Svc}Function"]["Properties"]
        find_in_map = inner_props["CodeUri"]["Fn::FindInMap"]
        self.assertEqual(find_in_map[0], "SAMCodeUriEnvsServices")
        # Compound key: should use Fn::Join
        self.assertIn("Fn::Join", find_in_map[1])
        self.assertEqual(find_in_map[1]["Fn::Join"][0], "-")
        self.assertEqual(find_in_map[1]["Fn::Join"][1], [{"Ref": "Env"}, {"Ref": "Svc"}])
        self.assertEqual(find_in_map[2], "CodeUri")


class TestMappingNameCollision(TestCase):
    """Tests for mapping name collision when multiple resources share the same property name in one ForEach loop.

    The mapping name suffix is derived from the resource logical ID template (resource_key)
    with loop variable placeholders stripped, not from the resource type.  This ensures
    uniqueness even when two resources of the *same* type collide.
    """

    def test_multiple_resources_same_property_name_in_same_foreach(self):
        """Two resources (Api and StateMachine) with DefinitionUri in the same loop produce separate Mappings."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        api_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}/swagger.yaml",
        )
        sm_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}StateMachine",
            resource_type="AWS::Serverless::StateMachine",
            property_name="DefinitionUri",
            property_value="statemachines/${Svc}/definition.asl.json",
        )
        exported_resources = {
            "usersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/users-api.yaml"},
            },
            "ordersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/orders-api.yaml"},
            },
            "usersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/users-sm.json"},
            },
            "ordersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/orders-sm.json"},
            },
        }
        mappings, prop_to_mapping = _generate_artifact_mappings([api_prop, sm_prop], "/tmp", exported_resources)
        # Should produce two separate mappings with resource-type suffixes
        self.assertIn("SAMDefinitionUriServicesApi", mappings)
        self.assertIn("SAMDefinitionUriServicesStateMachine", mappings)
        self.assertNotIn("SAMDefinitionUriServices", mappings)

        # Verify mapping contents are correct and not mixed up
        self.assertEqual(
            mappings["SAMDefinitionUriServicesApi"]["users"]["DefinitionUri"],
            "s3://bucket/users-api.yaml",
        )
        self.assertEqual(
            mappings["SAMDefinitionUriServicesApi"]["orders"]["DefinitionUri"],
            "s3://bucket/orders-api.yaml",
        )
        self.assertEqual(
            mappings["SAMDefinitionUriServicesStateMachine"]["users"]["DefinitionUri"],
            "s3://bucket/users-sm.json",
        )
        self.assertEqual(
            mappings["SAMDefinitionUriServicesStateMachine"]["orders"]["DefinitionUri"],
            "s3://bucket/orders-sm.json",
        )

        # property_to_mapping should use _prop_identity() as key
        self.assertEqual(
            prop_to_mapping[_prop_identity(api_prop)],
            "SAMDefinitionUriServicesApi",
        )
        self.assertEqual(
            prop_to_mapping[_prop_identity(sm_prop)],
            "SAMDefinitionUriServicesStateMachine",
        )

    def test_multiple_resources_same_property_name_findmap_replacement(self):
        """Each resource gets Fn::FindInMap pointing to its own Mapping when collision exists."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        api_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}/swagger.yaml",
        )
        sm_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}StateMachine",
            resource_type="AWS::Serverless::StateMachine",
            property_name="DefinitionUri",
            property_value="statemachines/${Svc}/definition.asl.json",
        )
        exported_resources = {
            "usersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/users-api.yaml"},
            },
            "ordersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/orders-api.yaml"},
            },
            "usersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/users-sm.json"},
            },
            "ordersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/orders-sm.json"},
            },
        }
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Svc",
                    ["users", "orders"],
                    {
                        "${Svc}Api": {
                            "Type": "AWS::Serverless::Api",
                            "Properties": {
                                "StageName": "prod",
                                "DefinitionUri": "apis/${Svc}/swagger.yaml",
                            },
                        },
                        "${Svc}StateMachine": {
                            "Type": "AWS::Serverless::StateMachine",
                            "Properties": {
                                "DefinitionUri": "statemachines/${Svc}/definition.asl.json",
                            },
                        },
                    },
                ]
            }
        }
        mappings, prop_to_mapping = _generate_artifact_mappings([api_prop, sm_prop], "/tmp", exported_resources)
        result = _apply_artifact_mappings_to_template(template, mappings, [api_prop, sm_prop], prop_to_mapping)

        body = result["Resources"]["Fn::ForEach::Services"][2]
        api_props = body["${Svc}Api"]["Properties"]
        sm_props = body["${Svc}StateMachine"]["Properties"]

        # Api should reference its own mapping
        self.assertEqual(
            api_props["DefinitionUri"]["Fn::FindInMap"][0],
            "SAMDefinitionUriServicesApi",
        )
        # StateMachine should reference its own mapping
        self.assertEqual(
            sm_props["DefinitionUri"]["Fn::FindInMap"][0],
            "SAMDefinitionUriServicesStateMachine",
        )

    def test_single_resource_per_property_name_backward_compatible(self):
        """Existing behavior unchanged: no suffix added when only one resource per property name."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Svc}",
        )
        exported_resources = {
            "UsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "OrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
        }
        mappings, prop_to_mapping = _generate_artifact_mappings([prop], "/tmp", exported_resources)
        # No suffix — only one resource with CodeUri
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertNotIn("SAMCodeUriServicesFunction", mappings)
        self.assertEqual(
            prop_to_mapping[_prop_identity(prop)],
            "SAMCodeUriServices",
        )

    def test_compute_mapping_name_no_collision(self):
        """_compute_mapping_name returns base name when no collision."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["A"],
            resource_key="${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}",
        )
        collision_groups = {("Services", "DefinitionUri"): 1}
        self.assertEqual(_compute_mapping_name(prop, collision_groups), "SAMDefinitionUriServices")

    def test_compute_mapping_name_with_collision(self):
        """_compute_mapping_name appends sanitized resource key suffix when collision detected."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["A"],
            resource_key="${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}",
        )
        collision_groups = {("Services", "DefinitionUri"): 2}
        # Suffix comes from resource_key "${Svc}Api" -> "Api"
        self.assertEqual(_compute_mapping_name(prop, collision_groups), "SAMDefinitionUriServicesApi")

    def test_same_type_different_resource_keys_no_collision(self):
        """Two functions with CodeUri in the same loop produce separate Mappings using resource key suffix."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        handler_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Handler",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="handlers/${Svc}/",
        )
        worker_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Worker",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="workers/${Svc}/",
        )
        exported_resources = {
            "usersHandler": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users-handler.zip"},
            },
            "ordersHandler": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders-handler.zip"},
            },
            "usersWorker": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users-worker.zip"},
            },
            "ordersWorker": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders-worker.zip"},
            },
        }
        mappings, prop_to_mapping = _generate_artifact_mappings([handler_prop, worker_prop], "/tmp", exported_resources)
        # Resource-type suffix would be "Function" for both — resource key suffix disambiguates
        self.assertIn("SAMCodeUriServicesHandler", mappings)
        self.assertIn("SAMCodeUriServicesWorker", mappings)
        self.assertNotIn("SAMCodeUriServices", mappings)
        self.assertNotIn("SAMCodeUriServicesFunction", mappings)

        # Verify mapping contents are correct
        self.assertEqual(
            mappings["SAMCodeUriServicesHandler"]["users"]["CodeUri"],
            "s3://bucket/users-handler.zip",
        )
        self.assertEqual(
            mappings["SAMCodeUriServicesWorker"]["orders"]["CodeUri"],
            "s3://bucket/orders-worker.zip",
        )

    def test_different_property_names_same_loop_no_collision(self):
        """Different property names in the same loop don't trigger collision detection."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        func_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="functions/${Svc}/",
        )
        api_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}/swagger.yaml",
        )
        exported_resources = {
            "usersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users-func.zip"},
            },
            "ordersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders-func.zip"},
            },
            "usersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/users-api.yaml"},
            },
            "ordersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/orders-api.yaml"},
            },
        }
        mappings, _ = _generate_artifact_mappings([func_prop, api_prop], "/tmp", exported_resources)
        # No collision — different property names get no suffix
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertIn("SAMDefinitionUriServices", mappings)
        self.assertNotIn("SAMCodeUriServicesFunction", mappings)
        self.assertNotIn("SAMDefinitionUriServicesApi", mappings)

    def test_empty_suffix_raises_invalid_template(self):
        """Resource keys with no static alphanumeric component raise InvalidTemplateException when collision exists."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop_a = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="a/${Svc}/",
        )
        prop_b = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["users", "orders"],
            resource_key="${Svc}",
            resource_type="AWS::Serverless::Api",
            property_name="CodeUri",
            property_value="b/${Svc}/",
        )
        exported_resources = {
            "users": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "orders": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
        }
        with self.assertRaises(InvalidTemplateException) as ctx:
            _generate_artifact_mappings([prop_a, prop_b], "/tmp", exported_resources)
        self.assertIn("empty suffix", str(ctx.exception))


class TestNestingPath(TestCase):
    """Tests for _nesting_path helper."""

    def test_nesting_path_non_nested(self):
        """Non-nested: outer_loops=[], returns loop_name."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["A"],
            resource_key="${Svc}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Svc}",
            outer_loops=[],
        )
        self.assertEqual(_nesting_path(prop), "Services")

    def test_nesting_path_single_level(self):
        """One outer loop returns 'OuterInner'."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Inner",
            loop_name="Inner",
            loop_variable="X",
            collection=["A"],
            resource_key="${X}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${X}",
            outer_loops=[("Fn::ForEach::Outer", "O", ["a", "b"])],
        )
        self.assertEqual(_nesting_path(prop), "OuterInner")

    def test_nesting_path_deep(self):
        """Two outer loops returns 'L1L2L3'."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::L3",
            loop_name="L3",
            loop_variable="Z",
            collection=["A"],
            resource_key="${Z}Func",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Z}",
            outer_loops=[
                ("Fn::ForEach::L1", "X", ["a"]),
                ("Fn::ForEach::L2", "Y", ["b"]),
            ],
        )
        self.assertEqual(_nesting_path(prop), "L1L2L3")


class TestCrossContextCollision(TestCase):
    """Tests for cross-context collision scenarios using nesting path."""

    def test_cross_context_same_inner_loop_name(self):
        """Two inner Fn::ForEach::Services under different parents produce different mapping names."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop_region = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Region}${Svc}StateMachine",
            resource_type="AWS::Serverless::StateMachine",
            property_name="DefinitionUri",
            property_value="statemachines/${Svc}/def.asl.json",
            outer_loops=[("Fn::ForEach::RegionAPIs", "Region", ["east", "west"])],
        )
        prop_env = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Env}${Svc}StateMachine",
            resource_type="AWS::Serverless::StateMachine",
            property_name="DefinitionUri",
            property_value="statemachines/${Svc}/def.asl.json",
            outer_loops=[("Fn::ForEach::EnvAPIs", "Env", ["dev", "prod"])],
        )
        exported_resources = {
            "eastUsersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/east-users-sm.json"},
            },
            "eastOrdersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/east-orders-sm.json"},
            },
            "devUsersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/dev-users-sm.json"},
            },
            "devOrdersStateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {"DefinitionUri": "s3://bucket/dev-orders-sm.json"},
            },
        }
        mappings, _ = _generate_artifact_mappings([prop_region, prop_env], "/tmp", exported_resources)
        # Different nesting paths produce different mapping names
        self.assertIn("SAMDefinitionUriRegionAPIsServices", mappings)
        self.assertIn("SAMDefinitionUriEnvAPIsServices", mappings)
        # Correct S3 URIs in each
        self.assertEqual(
            mappings["SAMDefinitionUriRegionAPIsServices"]["Users"]["DefinitionUri"],
            "s3://bucket/east-users-sm.json",
        )
        self.assertEqual(
            mappings["SAMDefinitionUriEnvAPIsServices"]["Users"]["DefinitionUri"],
            "s3://bucket/dev-users-sm.json",
        )

    def test_toplevel_and_nested_same_loop_name(self):
        """Top-level + nested Fn::ForEach::Services produce different mapping names."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        toplevel_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Svc}",
            outer_loops=[],
        )
        nested_prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Auth", "Notify"],
            resource_key="${Env}${Svc}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./nested/${Svc}",
            outer_loops=[("Fn::ForEach::Envs", "Env", ["dev", "prod"])],
        )
        exported_resources = {
            "UsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "OrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
            "devAuthFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/dev-auth.zip"},
            },
            "devNotifyFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/dev-notify.zip"},
            },
        }
        mappings, _ = _generate_artifact_mappings([toplevel_prop, nested_prop], "/tmp", exported_resources)
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertIn("SAMCodeUriEnvsServices", mappings)
        self.assertEqual(
            mappings["SAMCodeUriServices"]["Users"]["CodeUri"],
            "s3://bucket/users.zip",
        )
        self.assertEqual(
            mappings["SAMCodeUriEnvsServices"]["Auth"]["CodeUri"],
            "s3://bucket/dev-auth.zip",
        )

    def test_cross_context_same_resource_key_suffix(self):
        """Nesting path alone disambiguates when both inner loops have the same resource key suffix."""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop_a = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Region}${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}/swagger.yaml",
            outer_loops=[("Fn::ForEach::RegionAPIs", "Region", ["east", "west"])],
        )
        prop_b = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Svc",
            collection=["Users", "Orders"],
            resource_key="${Env}${Svc}Api",
            resource_type="AWS::Serverless::Api",
            property_name="DefinitionUri",
            property_value="apis/${Svc}/swagger.yaml",
            outer_loops=[("Fn::ForEach::EnvAPIs", "Env", ["dev", "prod"])],
        )
        exported_resources = {
            "eastUsersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/east-users-api.yaml"},
            },
            "eastOrdersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/east-orders-api.yaml"},
            },
            "devUsersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/dev-users-api.yaml"},
            },
            "devOrdersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/dev-orders-api.yaml"},
            },
        }
        mappings, _ = _generate_artifact_mappings([prop_a, prop_b], "/tmp", exported_resources)
        # Nesting path alone disambiguates — no resource-key suffix needed
        self.assertIn("SAMDefinitionUriRegionAPIsServices", mappings)
        self.assertIn("SAMDefinitionUriEnvAPIsServices", mappings)
        # No suffixed variants
        self.assertNotIn("SAMDefinitionUriRegionAPIsServicesApi", mappings)
        self.assertNotIn("SAMDefinitionUriEnvAPIsServicesApi", mappings)
