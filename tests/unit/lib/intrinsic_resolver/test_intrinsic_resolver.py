import json
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException


class TestIntrinsicFnJoinResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_join(self):
        intrinsic = {"Fn::Join": [",", ["a", "b", "c", "d"]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "a,b,c,d")

    def test_nested_fn_join(self):
        intrinsic_base_1 = {"Fn::Join": [",", ["a", "b", "c", "d"]]}
        intrinsic_base_2 = {"Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]}
        intrinsic = {"Fn::Join": [":", [intrinsic_base_1, "e", "f", intrinsic_base_2]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "a,b,c,d:e:f:g;h;i;a,b,c,d")

    @parameterized.expand(
        [
            ("Fn::Join should fail for values that are not lists: {}".format(item), item)
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_join_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Join should fail if the first argument does not resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_join_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": [delimiter, []]}, True)

    @parameterized.expand(
        [
            ("Fn::Join should fail if the list_of_objects is not a valid list: {}".format(item), item)
            for item in [True, False, {}, 42, "t", None]
        ]
    )
    def test_fn_list_of_objects_invalid_type(self, name, list_of_objects):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": ["", list_of_objects]}, True)

    @parameterized.expand(
        [
            ("Fn::Join should require that all items in the list_of_objects resolve to string: {}".format(item), item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_join_items_all_str(self, name, single_obj):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": ["", ["test", single_obj, "abcd"]]}, True)


class TestIntrinsicFnSplitResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {"Fn::Split": ["|", "a|b|c"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, ["a", "b", "c"])

    def test_nested_fn_split(self):
        intrinsic_base_1 = {"Fn::Split": [";", {"Fn::Join": [";", ["a", "b", "c"]]}]}

        intrinsic_base_2 = {"Fn::Join": [",", intrinsic_base_1]}
        intrinsic = {"Fn::Split": [",", {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, ["a", "b", "c", "", "e", "", "f", "", "a", "b", "c"])

    @parameterized.expand(
        [
            ("Fn::Split should fail for values that are not lists: {}".format(item), item)
            for item in [True, False, "Test", {}, 42]
        ]
    )
    def test_fn_split_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Split": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Split should fail if the first argument does not resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42]
        ]
    )
    def test_fn_split_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Split": [delimiter, []]}, True)

    @parameterized.expand(
        [
            ("Fn::Split should fail if the second argument does not resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42]
        ]
    )
    def test_fn_split_source_string_invalid_type(self, name, source_string):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Split": ["", source_string]}, True)


class TestIntrinsicFnBase64Resolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {"Fn::Base64": "AWS CloudFormation"}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "QVdTIENsb3VkRm9ybWF0aW9u")

    def test_nested_fn_base64(self):
        intrinsic_base_1 = {"Fn::Base64": "AWS CloudFormation"}

        intrinsic_base_2 = {"Fn::Base64": intrinsic_base_1}
        intrinsic = {"Fn::Base64": {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(
            result,
            "VVZaa1ZFbEZUbk5pTTFaclVtMDVlV0pYUmpCaFZ6bDEsLGUsLGYsLFVWWmtWRWxGVG5OaU0xWnJ" "VbTA1ZVdKWFJqQmhWemwx",
        )

    @parameterized.expand(
        [
            ("Fn::Base64 must have a value that resolves to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_base64_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Base64": intrinsic}, True)


class TestIntrinsicFnSelectResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_select(self):
        intrinsic = {"Fn::Select": [2, ["a", "b", "c", "d"]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "c")

    def test_nested_fn_select(self):
        intrinsic_base_1 = {"Fn::Select": [0, ["a", "b", "c", "d"]]}
        intrinsic_base_2 = {"Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]}
        intrinsic = {"Fn::Select": [3, [intrinsic_base_2, "e", "f", intrinsic_base_2]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "g;h;i;a")

    @parameterized.expand(
        [
            ("Fn::Select should fail for values that are not lists: {}".format(item), item)
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_select_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Select should fail if the first argument does not resolve to a int: {}".format(item), item)
            for item in [True, False, {}, "3", None]
        ]
    )
    def test_fn_select_index_invalid_index_type(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [index, [0]]}, True)

    @parameterized.expand(
        [("Fn::Select should fail if the index is out of bounds: {}".format(number), number) for number in [-2, 7]]
    )
    def test_fn_select_out_of_bounds(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [index, []]}, True)

    @parameterized.expand(
        [
            ("Fn::Select should fail if the second argument does not resolve to a list: {}".format(item), item)
            for item in [True, False, {}, "3", 33, None]
        ]
    )
    def test_fn_select_second_argument_invalid_type(self, name, argument):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [0, argument]}, True)


class TestIntrinsicFnFindInMapResolver(TestCase):
    def setUp(self):
        template = {
            "Mappings": {
                "Basic": {"Test": {"key": "value"}},
                "value": {"anotherkey": {"key": "result"}},
                "result": {"value": {"key": "final"}},
            }
        }
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable(), template=template)

    def test_basic_find_in_map(self):
        intrinsic = {"Fn::FindInMap": ["Basic", "Test", "key"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "value")

    def test_nested_find_in_map(self):
        intrinsic_base_1 = {"Fn::FindInMap": ["Basic", "Test", "key"]}
        intrinsic_base_2 = {"Fn::FindInMap": [intrinsic_base_1, "anotherkey", "key"]}
        intrinsic = {"Fn::FindInMap": [intrinsic_base_2, intrinsic_base_1, "key"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "final")

    @parameterized.expand(
        [
            ("Fn::FindInMap should fail if the list does not resolve to a string: {}".format(item), item)
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_find_in_map_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::FindInMap should fail if there isn't 3 arguments in the list: {}".format(item), item)
            for item in [[""] * i for i in [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_find_in_map_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic}, True)

    @parameterized.expand(
        [
            (
                f"The arguments in Fn::FindInMap must fail if the arguments are not in the mappings: {item}",
                item,
            )
            for item in [
                ["<UNKOWN_VALUE>", "Test", "key"],
                ["Basic", "<UNKOWN_VALUE>", "key"],
                ["Basic", "Test", "<UNKOWN_VALUE>"],
            ]
        ]
    )
    def test_fn_find_in_map_invalid_key_entries(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic}, True)


class TestIntrinsicFnAzsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"AWS::Region": "us-east-1"}
        self.resolver = IntrinsicResolver(
            template={}, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator)
        )

    def test_basic_azs(self):
        intrinsic = {"Ref": "AWS::Region"}
        result = self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic}, True)
        self.assertEqual(result, ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"])

    def test_default_get_azs(self):
        result = self.resolver.intrinsic_property_resolver({"Fn::GetAZs": ""}, True)
        self.assertEqual(result, ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"])

    @parameterized.expand(
        [
            (f"Fn::GetAZs should fail if it not given a string type: {item}", item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_azs_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic}, True)

    def test_fn_azs_invalid_region(self):
        intrinsic = "UNKOWN REGION"
        with self.assertRaises(InvalidIntrinsicException, msg="FN::GetAzs should fail for unknown region"):
            self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic}, True)


class TestFnTransform(TestCase):
    def setUp(self):
        logical_id_translator = {"AWS::Region": "us-east-1"}
        self.resolver = IntrinsicResolver(
            template={}, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator)
        )

    @patch("samcli.lib.intrinsic_resolver.intrinsic_property_resolver.get_template_data")
    def test_basic_fn_transform(self, get_template_data_patch):
        intrinsic = {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": "test"}}}
        get_template_data_patch.return_value = {"data": "test"}
        self.resolver.intrinsic_property_resolver(intrinsic, True)
        get_template_data_patch.assert_called_once_with("test")

    def test_fn_transform_unsupported_macro(self):
        intrinsic = {"Fn::Transform": {"Name": "UNKNOWN", "Parameters": {"Location": "test"}}}
        with self.assertRaises(InvalidIntrinsicException, msg="FN::Transform should fail for unknown region"):
            self.resolver.intrinsic_property_resolver(intrinsic, True)


class TestIntrinsicFnRefResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"RestApi": {"Ref": "NewRestApi"}, "AWS::StackId": "12301230123"}
        resources = {"RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {}}}
        template = {"Resources": resources}
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, template=template),
            template=template,
        )

    def test_basic_ref_translation(self):
        intrinsic = {"Ref": "RestApi"}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "NewRestApi")

    def test_default_ref_translation(self):
        intrinsic = {"Ref": "UnknownApi"}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "UnknownApi")

    @parameterized.expand(
        [
            ("Ref must have arguments that resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None, []]
        ]
    )
    def test_ref_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Ref": intrinsic}, True)


class TestIntrinsicFnGetAttResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "RestApi": {"Ref": "NewRestApi"},
            "LambdaFunction": {
                "Arn": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                "-1:123456789012:LambdaFunction/invocations"
            },
            "AWS::StackId": "12301230123",
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "406033500479",
        }
        resources = {
            "RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {}},
            "HelloHandler2E4FBA4D": {"Type": "AWS::Lambda::Function", "Properties": {"handler": "main.handle"}},
            "LambdaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Uri": {
                        "Fn::Join": [
                            "",
                            [
                                "arn:",
                                {"Ref": "AWS::Partition"},
                                ":apigateway:",
                                {"Ref": "AWS::Region"},
                                ":lambda:path/2015-03-31/functions/",
                                {"Fn::GetAtt": ["HelloHandler2E4FBA4D", "Arn"]},
                                "/invocations",
                            ],
                        ]
                    }
                },
            },
            "LambdaFunctionWithFunctionName": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"FunctionName": "lambda-function-with-function-name", "handler": "main.handle"},
            },
            "ReferencingLambdaFunctionWithFunctionName": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Uri": {"Fn::GetAtt": ["LambdaFunctionWithFunctionName", "Arn"]}},
            },
        }
        template = {"Resources": resources}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=logical_id_translator)
        self.resources = resources
        self.resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)

    def test_fn_getatt_basic_translation(self):
        intrinsic = {"Fn::GetAtt": ["RestApi", "RootResourceId"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "/")

    def test_fn_getatt_logical_id_translated(self):
        intrinsic = {"Fn::GetAtt": ["LambdaFunction", "Arn"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
            "-1:123456789012:LambdaFunction/invocations",
        )

    def test_fn_getatt_with_fn_join(self):
        intrinsic = self.resources.get("LambdaFunction").get("Properties").get("Uri")
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us"
            "-east-1:406033500479:function:HelloHandler2E4FBA4D/invocations",
        )

    def test_fn_getatt_with_lambda_function_with_function_name(self):
        intrinsic = self.resources.get("ReferencingLambdaFunctionWithFunctionName").get("Properties").get("Uri")
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(result, "arn:aws:lambda:us-east-1:406033500479:function:lambda-function-with-function-name")

    @parameterized.expand(
        [
            ("Fn::GetAtt must fail if the argument does not resolve to a list: {}".format(item), item)
            for item in [True, False, {}, "test", 42, None]
        ]
    )
    def test_fn_getatt_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::GetAtt should fail if it doesn't have exactly 2 arguments: {}".format(item), item)
            for item in [[""] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_getatt_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::GetAtt first argument must resolve to a valid string: {}".format(item), item)
            for item in [True, False, {}, [], 42, None]
        ]
    )
    def test_fn_getatt_first_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": [intrinsic, IntrinsicResolver.REF]}, True)

    @parameterized.expand(
        [
            ("Fn::GetAtt second argument must resolve to a string:{}".format(item), item)
            for item in [True, False, {}, [], 42, None]
        ]
    )
    def test_fn_getatt_second_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": ["some logical Id", intrinsic]}, True)


class TestIntrinsicFnSubResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"AWS::Region": "us-east-1", "AWS::AccountId": "123456789012"}
        resources = {"LambdaFunction": {"Type": "AWS::ApiGateway::RestApi", "Properties": {"Uri": "test"}}}
        template = {"Resources": resources}
        self.resolver = IntrinsicResolver(
            template=template,
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, template=template),
        )

    def test_fn_sub_basic_uri(self):
        intrinsic = {
            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaFunction.Arn}/invocations"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1"
            ":123456789012:function:LambdaFunction/invocations",
        )

    def test_fn_sub_uri_arguments(self):
        intrinsic = {
            "Fn::Sub": [
                "arn:aws:apigateway:${MyItem}:lambda:path/2015-03-31/functions/${MyOtherItem}/invocations",
                {"MyItem": {"Ref": "AWS::Region"}, "MyOtherItem": "LambdaFunction.Arn"},
            ]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
            "-1:123456789012:function:LambdaFunction/invocations",
        )

    @parameterized.expand(
        [
            (f"Fn::Sub arguments must either resolve to a string or a list: {item}", item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_sub_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": intrinsic}, True)

    @parameterized.expand(
        [
            ("If Fn::Sub is a list, first argument must resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_sub_first_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": [intrinsic, {}]}, True)

    @parameterized.expand(
        [
            (f"If Fn::Sub is a list, second argument must resolve to a dictionary {item}", item)
            for item in [True, False, "Another str", [], 42, None]
        ]
    )
    def test_fn_sub_second_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": ["some str", intrinsic]}, True)

    @parameterized.expand(
        [
            (f"If Fn::Sub is a list, it should only have 2 arguments {item}", item)
            for item in [[""] * i for i in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_sub_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": ["test"] + intrinsic}, True)


class TestIntrinsicFnImportValueResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_fn_import_value_unsupported(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Fn::ImportValue should be unsupported"):
            self.resolver.intrinsic_property_resolver({"Fn::ImportValue": ""}, True)


class TestIntrinsicFnEqualsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"EnvironmentType": "prod", "AWS::AccountId": "123456789012"}
        self.resolver = IntrinsicResolver(
            template={}, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator)
        )

    def test_fn_equals_basic_true(self):
        intrinsic = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_equals_basic_false(self):
        intrinsic = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "NotProd"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_equals_nested_true(self):
        intrinsic_base_1 = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base_2 = {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}

        intrinsic = {"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_equals_nested_false(self):
        intrinsic_base_1 = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base_2 = {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "NOT_A_VALID_ACCOUNT_ID"]}

        intrinsic = {"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::Equals must have arguments that resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_equals_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Equals": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Equals must have exactly two arguments: {}".format(item), item)
            for item in [["t"] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_equals_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Equals": intrinsic}, True)


class TestIntrinsicFnNotResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"EnvironmentType": "prod", "AWS::AccountId": "123456789012"}
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=logical_id_translator)
        self.resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)

    def test_fn_not_basic_false(self):
        intrinsic = {"Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_not_basic_true(self):
        intrinsic = {"Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "NotProd"]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_not_nested_true(self):
        intrinsic_base_1 = {"Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]}
        intrinsic_base_2 = {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}
        # !(True && True)
        intrinsic = {"Fn::Not": [{"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_not_nested_false(self):
        intrinsic_base_1 = {"Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]}
        intrinsic_base_2 = {"Fn::Not": [{"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}]}

        intrinsic = {"Fn::Not": [{"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_not_condition_false(self):
        intrinsic = {"Fn::Not": [{"Condition": "TestCondition"}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_not_condition_true(self):
        intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    @parameterized.expand(
        [
            ("Fn::Not must have an argument that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_not_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Not items in the list must resolve to booleans: {}".format(item), item)
            for item in [{}, 42, None, "test"]
        ]
    )
    def test_fn_not_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": [intrinsic]}, True)

    @parameterized.expand(
        [
            ("Fn::Not must have exactly 1 argument: {}".format(item), item)
            for item in [[True] * i for i in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_not_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": intrinsic}, True)

    def test_fn_not_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({"Fn::Not": [{"Condition": "NOT_VALID_CONDITION"}]}, True)


class TestIntrinsicFnAndResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"EnvironmentType": "prod", "AWS::AccountId": "123456789012"}
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=logical_id_translator)
        self.resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)

    def test_fn_and_basic_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {"Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_and_basic_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {"Fn::And": [prod_fn_equals, {"Condition": "NotTestCondition"}, prod_fn_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_and_nested_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base = {"Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]}
        fn_not_intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        intrinsic = {"Fn::And": [intrinsic_base, fn_not_intrinsic, prod_fn_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_and_nested_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        prod_fn_not_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "NOT_EQUAL"]}
        intrinsic_base = {"Fn::And": [prod_fn_equals, {"Condition": "NotTestCondition"}, prod_fn_equals]}
        intrinsic = {"Fn::And": [{"Fn::Not": [intrinsic_base]}, prod_fn_not_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::And must have value that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_and_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::And": intrinsic}, True)

    @parameterized.expand(
        [(f"Fn:And must have all arguments that resolves to booleans {item}", item) for item in [{}, 42, None, "test"]]
    )
    def test_fn_and_all_arguments_bool(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::And": [intrinsic, intrinsic, intrinsic]}, True)

    def test_fn_and_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({"Fn::And": [{"Condition": "NOT_VALID_CONDITION"}]}, True)


class TestIntrinsicFnOrResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"EnvironmentType": "prod", "AWS::AccountId": "123456789012"}
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }

        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=logical_id_translator)
        self.resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)

    def test_fn_or_basic_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {"Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_or_basic_single_true(self):
        intrinsic = {"Fn::Or": [False, False, {"Condition": "TestCondition"}, False]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_or_basic_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_fn_or_nested_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        failed_intrinsic_or = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        intrinsic_base = {"Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]}
        fn_not_intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        intrinsic = {"Fn::Or": [failed_intrinsic_or, intrinsic_base, fn_not_intrinsic, fn_not_intrinsic]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_or_nested_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        failed_intrinsic_or = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        intrinsic_base = {"Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]}
        intrinsic = {"Fn::Or": [failed_intrinsic_or, {"Fn::Not": [intrinsic_base]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::Or must have an argument that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_or_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Or": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::Or must have all arguments resolve to booleans: {}".format(item), item)
            for item in [{}, 42, None, "test"]
        ]
    )
    def test_fn_or_all_arguments_bool(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Or": [intrinsic, intrinsic, intrinsic]}, True)

    def test_fn_or_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({"Fn::Or": [{"Condition": "NOT_VALID_CONDITION"}]}, True)


class TestIntrinsicFnIfResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"EnvironmentType": "prod", "AWS::AccountId": "123456789012"}
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
            "InvalidCondition": ["random items"],
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=logical_id_translator)
        self.resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)

    def test_fn_if_basic_true(self):
        intrinsic = {"Fn::If": ["TestCondition", True, False]}

        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_fn_if_basic_false(self):
        intrinsic = {"Fn::If": ["NotTestCondition", True, False]}

        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    def test_nested_fn_if_true(self):
        intrinsic_base_1 = {"Fn::If": ["NotTestCondition", True, False]}
        intrinsic_base_2 = {"Fn::If": ["TestCondition", True, False]}
        intrinsic = {"Fn::If": ["TestCondition", intrinsic_base_2, intrinsic_base_1]}

        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertTrue(result)

    def test_nested_fn_if_false(self):
        intrinsic_base_1 = {"Fn::If": ["NotTestCondition", True, False]}
        intrinsic_base_2 = {"Fn::If": ["TestCondition", True, False]}
        intrinsic = {"Fn::If": ["TestCondition", intrinsic_base_1, intrinsic_base_2]}

        result = self.resolver.intrinsic_property_resolver(intrinsic, True)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::If must an argument that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_if_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::If": intrinsic}, True)

    @parameterized.expand(
        [
            ("Fn::If must have the argument resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test", []]
        ]
    )
    def test_fn_if_condition_arguments_invalid_type(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::If": [intrinsic, True, False]}, True)

    def test_fn_if_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({"Fn::If": ["NOT_VALID_CONDITION", "test", "test"]}, True)

    @parameterized.expand(
        [
            ("Fn::If must have exactly 3 arguments: {}".format(item), item)
            for item in [[True] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_if_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": ["TestCondition"] + intrinsic}, True)

    def test_fn_if_condition_not_bool_fail(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({"Fn::If": ["InvalidCondition", "test", "test"]}, True)


class TestIntrinsicAttribteResolution(TestCase):
    def setUp(self):
        self.maxDiff = None
        logical_id_translator = {
            "RestApi": "NewRestApi",
            "LambdaFunction": {
                "Arn": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                "-1:123456789012:LambdaFunction/invocations"
            },
            "AWS::StackId": "12301230123",
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "406033500479",
            "RestApi.Deployment": {"Ref": "RestApi"},
        }
        self.logical_id_translator = logical_id_translator

        integration_path = str(
            Path(__file__).resolve().parents[0].joinpath("test_data", "inputs/test_intrinsic_template_resolution.json")
        )
        with open(integration_path) as f:
            template = json.load(f)

        self.template = template
        self.resources = template.get("Resources")
        self.conditions = template.get("Conditions")
        self.mappings = template.get("Mappings")

        symbol_resolver = IntrinsicsSymbolTable(
            template=self.template, logical_id_translator=self.logical_id_translator
        )
        self.resolver = IntrinsicResolver(template=self.template, symbol_resolver=symbol_resolver)

    def test_basic_attribte_resolution(self):
        resolved_template = self.resolver.resolve_attribute(self.resources, ignore_errors=False)

        expected_resources = {
            "HelloHandler2E4FBA4D": {"Properties": {"handler": "main.handle"}, "Type": "AWS::Lambda::Function"},
            "LambdaFunction": {
                "Properties": {
                    "Uri": "arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31/functions/arn:aws"
                    ":lambda:us-east-1:406033500479:function:HelloHandler2E4FBA4D/invocations"
                },
                "Type": "AWS::Lambda::Function",
            },
            "ReferenceLambdaLayerVersionLambdaFunction": {
                "Properties": {
                    "Handler": "layer-main.custom_layer_handler",
                    "Runtime": "python3.9",
                    "CodeUri": ".",
                    "Layers": [{"Ref": "MyCustomLambdaLayer"}],
                },
                "Type": "AWS::Serverless::Function",
            },
            "MyCustomLambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "custom_layer/"}},
            "RestApi": {
                "Properties": {"Body": "YTtlO2Y7ZA==", "BodyS3Location": "https://s3location/"},
                "Type": "AWS::ApiGateway::RestApi",
            },
            "RestApiResource": {"Properties": {"PathPart": "{proxy+}", "RestApiId": "RestApi", "parentId": "/"}},
        }
        self.assertEqual(dict(resolved_template), expected_resources)

    def test_template_fail_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {"Fn::FindInMap": []}
        template = {"Mappings": self.mappings, "Conditions": self.conditions, "Resources": resources}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=self.logical_id_translator)
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Find In Map"):
            resolver.resolve_attribute(resources, ignore_errors=False)

    def test_template_ignore_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {"Fn::FindInMap": []}
        template = {"Mappings": self.mappings, "Conditions": self.conditions, "Resources": resources}
        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator=self.logical_id_translator)
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        result = resolver.resolve_attribute(resources, ignore_errors=True)
        expected_template = {
            "HelloHandler2E4FBA4D": {"Properties": {"handler": "main.handle"}, "Type": "AWS::Lambda::Function"},
            "ReferenceLambdaLayerVersionLambdaFunction": {
                "Properties": {
                    "Handler": "layer-main.custom_layer_handler",
                    "Runtime": "python3.9",
                    "CodeUri": ".",
                    "Layers": [{"Ref": "MyCustomLambdaLayer"}],
                },
                "Type": "AWS::Serverless::Function",
            },
            "MyCustomLambdaLayer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "custom_layer/"}},
            "LambdaFunction": {
                "Properties": {
                    "Uri": "arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31"
                    "/functions/arn:aws:lambda:us-east-1:406033500479"
                    ":function:HelloHandler2E4FBA4D/invocations"
                },
                "Type": "AWS::Lambda::Function",
            },
            "RestApi": {
                "Properties": {"Body": "YTtlO2Y7ZA==", "BodyS3Location": {"Fn::FindInMap": []}},
                "Type": "AWS::ApiGateway::RestApi",
            },
            "RestApiResource": {"Properties": {"PathPart": "{proxy+}", "RestApiId": "RestApi", "parentId": "/"}},
        }
        self.assertEqual(expected_template, dict(result))


class TestResolveTemplate(TestCase):
    def test_parameter_not_resolved(self):
        template = {
            "Parameters": {"TestStageName": {"Default": "test", "Type": "string"}},
            "Resources": {
                "Test": {"Type": "AWS::ApiGateway::RestApi", "Parameters": {"StageName": {"Ref": "TestStageName"}}}
            },
        }

        expected_template = {
            "Parameters": {"TestStageName": {"Default": "test", "Type": "string"}},
            "Resources": OrderedDict(
                {"Test": {"Type": "AWS::ApiGateway::RestApi", "Parameters": {"StageName": "test"}}}
            ),
        }

        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator={})
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        self.assertEqual(resolver.resolve_template(), expected_template)

    def test_mappings_directory_resolved(self):
        template = {
            "Mappings": {"TestStageName": {"TestKey": {"key": "StageName"}}},
            "Resources": {
                "Test": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Parameters": {"StageName": {"Fn::FindInMap": ["TestStageName", "TestKey", "key"]}},
                }
            },
        }

        expected_template = {
            "Mappings": {"TestStageName": {"TestKey": {"key": "StageName"}}},
            "Resources": OrderedDict(
                {"Test": {"Type": "AWS::ApiGateway::RestApi", "Parameters": {"StageName": "StageName"}}}
            ),
        }

        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator={})
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        self.assertEqual(resolver.resolve_template(), expected_template)

    def test_output_resolved(self):
        template = {
            "Parameters": {"StageRef": {"Default": "StageName"}},
            "Outputs": {"TestStageName": {"Ref": "Test"}, "ParameterRef": {"Ref": "StageRef"}},
            "Resources": {
                "Test": {"Type": "AWS::ApiGateway::RestApi", "Parameters": {"StageName": {"Ref": "StageRef"}}}
            },
        }

        expected_template = {
            "Parameters": {"StageRef": {"Default": "StageName"}},
            "Resources": OrderedDict(
                {"Test": {"Type": "AWS::ApiGateway::RestApi", "Parameters": {"StageName": "StageName"}}}
            ),
            "Outputs": OrderedDict({"TestStageName": "Test", "ParameterRef": "StageName"}),
        }

        symbol_resolver = IntrinsicsSymbolTable(template=template, logical_id_translator={})
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        self.assertEqual(resolver.resolve_template(), expected_template)

    def load_test_data(self, template_path):
        integration_path = str(Path(__file__).resolve().parents[0].joinpath("test_data", template_path))
        with open(integration_path) as f:
            template = json.load(f)
        return template

    @parameterized.expand(
        [
            (
                "inputs/test_intrinsic_template_resolution.json",
                "outputs/output_test_intrinsic_template_resolution.json",
            ),
            ("inputs/test_layers_resolution.json", "outputs/outputs_test_layers_resolution.json"),
            ("inputs/test_methods_resource_resolution.json", "outputs/outputs_methods_resource_resolution.json"),
        ]
    )
    def test_intrinsic_sample_inputs_outputs(self, input, output):
        input_template = self.load_test_data(input)
        symbol_resolver = IntrinsicsSymbolTable(template=input_template, logical_id_translator={})
        resolver = IntrinsicResolver(template=input_template, symbol_resolver=symbol_resolver)
        processed_template = resolver.resolve_template()
        processed_template = json.loads(json.dumps(processed_template))  # Removes formatting of ordered dicts
        expected_template = self.load_test_data(output)
        self.assertEqual(processed_template, expected_template)


class TestIntrinsicResolverInitialization(TestCase):
    def test_conditional_key_function_map(self):
        resolver = IntrinsicResolver(None, None)

        def lambda_func(x):
            return True

        resolver.set_conditional_function_map({"key": lambda_func})
        self.assertTrue(resolver.conditional_key_function_map.get("key") == lambda_func)

    def test_set_intrinsic_key_function_map(self):
        resolver = IntrinsicResolver(None, None)

        def lambda_func(x):
            return True

        resolver.set_intrinsic_key_function_map({"key": lambda_func})
        self.assertTrue(resolver.intrinsic_key_function_map.get("key") == lambda_func)
