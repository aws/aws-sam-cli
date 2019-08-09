import json
from copy import deepcopy
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path
from unittest import TestCase

from parameterized import parameterized

from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import (
    InvalidIntrinsicException,
)


class TestIntrinsicFnJoinResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_join(self):
        intrinsic = {"Fn::Join": [",", ["a", "b", "c", "d"]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "a,b,c,d")

    def test_nested_fn_join(self):
        intrinsic_base_1 = {"Fn::Join": [",", ["a", "b", "c", "d"]]}
        intrinsic_base_2 = {"Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]}
        intrinsic = {"Fn::Join": [":", [intrinsic_base_1, "e", "f", intrinsic_base_2]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "a,b,c,d:e:f:g;h;i;a,b,c,d")

    @parameterized.expand(
        [
            (
                    "Fn::Join should fail for values that are not lists: {}".format(item),
                    item,
            )
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_join_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::Join should fail if the first argument does not resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_join_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Join": [delimiter, []]})

    @parameterized.expand(
        [
            (
                    "Fn::Join should fail if the list_of_objects is not a valid list: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, "t", None]
        ]
    )
    def test_fn_list_of_objects_invalid_type(self, name, list_of_objects):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Join": ["", list_of_objects]}
            )

    @parameterized.expand(
        [
            (
                    "Fn::Join should require that all items in the list_of_objects resolve to string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_join_items_all_str(self, name, single_obj):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Join": ["", ["test", single_obj, "abcd"]]}
            )


class TestIntrinsicFnSplitResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {"Fn::Split": ["|", "a|b|c"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, ["a", "b", "c"])

    def test_nested_fn_split(self):
        intrinsic_base_1 = {"Fn::Split": [";", {"Fn::Join": [";", ["a", "b", "c"]]}]}

        intrinsic_base_2 = {"Fn::Join": [",", intrinsic_base_1]}
        intrinsic = {
            "Fn::Split": [
                ",",
                {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]},
            ]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, ["a", "b", "c", "", "e", "", "f", "", "a", "b", "c"])

    @parameterized.expand(
        [
            (
                    "Fn::Split should fail for values that are not lists: {}".format(item),
                    item,
            )
            for item in [True, False, "Test", {}, 42]
        ]
    )
    def test_fn_split_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Split": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::Split should fail if the first argument does not resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42]
        ]
    )
    def test_fn_split_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Split": [delimiter, []]})

    @parameterized.expand(
        [
            (
                    "Fn::Split should fail if the second argument does not resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42]
        ]
    )
    def test_fn_split_source_string_invalid_type(self, name, source_string):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Split": ["", source_string]}
            )


class TestIntrinsicFnBase64Resolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {"Fn::Base64": "AWS CloudFormation"}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "QVdTIENsb3VkRm9ybWF0aW9u")

    def test_nested_fn_base64(self):
        intrinsic_base_1 = {"Fn::Base64": "AWS CloudFormation"}

        intrinsic_base_2 = {"Fn::Base64": intrinsic_base_1}
        intrinsic = {
            "Fn::Base64": {
                "Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]
            }
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(
            result,
            "VVZaa1ZFbEZUbk5pTTFaclVtMDVlV0pYUmpCaFZ6bDEsLGUsLGYsLFVWWmtWRWxGVG5OaU0xWnJ"
            "VbTA1ZVdKWFJqQmhWemwx",
        )

    @parameterized.expand(
        [
            (
                    "Fn::Base64 must have a value that resolves to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_base64_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Base64": intrinsic})


class TestIntrinsicFnSelectResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_select(self):
        intrinsic = {"Fn::Select": [2, ["a", "b", "c", "d"]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "c")

    def test_nested_fn_select(self):
        intrinsic_base_1 = {"Fn::Select": [0, ["a", "b", "c", "d"]]}
        intrinsic_base_2 = {"Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]}
        intrinsic = {"Fn::Select": [3, [intrinsic_base_2, "e", "f", intrinsic_base_2]]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "g;h;i;a")

    @parameterized.expand(
        [
            (
                    "Fn::Select should fail for values that are not lists: {}".format(item),
                    item,
            )
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_select_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::Select should fail if the first argument does not resolve to a int: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, "3", None]
        ]
    )
    def test_fn_select_index_invalid_index_type(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [index, [0]]})

    @parameterized.expand(
        [
            (
                    "Fn::Select should fail if the index is out of bounds: {}".format(
                        number
                    ),
                    number,
            )
            for number in [-2, 7]
        ]
    )
    def test_fn_select_out_of_bounds(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [index, []]})

    @parameterized.expand(
        [
            (
                    "Fn::Select should fail if the second argument does not resolve to a list: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, "3", 33, None]
        ]
    )
    def test_fn_select_second_argument_invalid_type(self, name, argument):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Select": [0, argument]})


class TestIntrinsicFnFindInMapResolver(TestCase):
    def setUp(self):
        template = {
            "Mappings": {
                "Basic": {"Test": {"key": "value"}},
                "value": {"anotherkey": {"key": "result"}},
                "result": {"value": {"key": "final"}},
            }
        }
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(), template=template
        )

    def test_basic_find_in_map(self):
        intrinsic = {"Fn::FindInMap": ["Basic", "Test", "key"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "value")

    def test_nested_find_in_map(self):
        intrinsic_base_1 = {"Fn::FindInMap": ["Basic", "Test", "key"]}
        intrinsic_base_2 = {"Fn::FindInMap": [intrinsic_base_1, "anotherkey", "key"]}
        intrinsic = {"Fn::FindInMap": [intrinsic_base_2, intrinsic_base_1, "key"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "final")

    @parameterized.expand(
        [
            (
                    "Fn::FindInMap should fail if the list does not resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, "Test", {}, 42, None]
        ]
    )
    def test_fn_find_in_map_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::FindInMap should fail if there isn't 3 arguments in the list: {}".format(
                        item
                    ),
                    item,
            )
            for item in [[""] * i for i in [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_find_in_map_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic})

    @parameterized.expand(
        [
            (
                    "The arguments in Fn::FindInMap must fail if the arguments are not in the mappings".format(
                        item
                    ),
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
            self.resolver.intrinsic_property_resolver({"Fn::FindInMap": intrinsic})


class TestIntrinsicFnAzsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {"AWS::Region": "us-east-1"}
        self.resolver = IntrinsicResolver(
            template={},
            symbol_resolver=IntrinsicsSymbolTable(
                logical_id_translator=logical_id_translator
            )
        )

    def test_basic_azs(self):
        intrinsic = {"Ref": "AWS::Region"}
        result = self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic})
        self.assertEqual(
            result,
            [
                "us-east-1a",
                "us-east-1b",
                "us-east-1c",
                "us-east-1d",
                "us-east-1e",
                "us-east-1f",
            ],
        )

    def test_default_get_azs(self):
        result = self.resolver.intrinsic_property_resolver({"Fn::GetAZs": ""})
        self.assertEqual(
            result,
            [
                "us-east-1a",
                "us-east-1b",
                "us-east-1c",
                "us-east-1d",
                "us-east-1e",
                "us-east-1f",
            ],
        )

    @parameterized.expand(
        [
            ("Fn::GetAZs should fail if it not given a string type".format(item), item)
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_azs_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic})

    def test_fn_azs_invalid_region(self):
        intrinsic = "UNKOWN REGION"
        with self.assertRaises(InvalidIntrinsicException, msg="FN::GetAzs should fail for unknown region"):
            self.resolver.intrinsic_property_resolver({"Fn::GetAZs": intrinsic})


class TestFnTransform(TestCase):
    def setUp(self):
        logical_id_translator = {"AWS::Region": "us-east-1"}
        self.resolver = IntrinsicResolver(
            template={},
            symbol_resolver=IntrinsicsSymbolTable(
                logical_id_translator=logical_id_translator
            )
        )

    def test_basic_fn_transform(self):
        intrinsic = {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": "test"}}}
        self.resolver.intrinsic_property_resolver(intrinsic)

    def test_fn_transform_unsupported_macro(self):
        intrinsic = {"Fn::Transform": {"Name": "UNKNOWN", "Parameters": {"Location": "test"}}}
        with self.assertRaises(InvalidIntrinsicException, msg="FN::Transform should fail for unknown region"):
            self.resolver.intrinsic_property_resolver(intrinsic)


class TestIntrinsicFnRefResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "RestApi": {"Ref": "NewRestApi"},
            "AWS::StackId": "12301230123",
        }
        resources = {"RestApi": {"Type": "AWS::ApiGateway::RestApi", "Properties": {}}}
        template = {"Resources": resources}
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(
                logical_id_translator=logical_id_translator, template=template
            ), template=template
        )

    def test_basic_ref_translation(self):
        intrinsic = {"Ref": "RestApi"}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "NewRestApi")

    def test_default_ref_translation(self):
        intrinsic = {"Ref": "UnknownApi"}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "UnknownApi")

    @parameterized.expand(
        [
            ("Ref must have arguments that resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None, []]
        ]
    )
    def test_ref_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Ref": intrinsic})


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
            "HelloHandler2E4FBA4D": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"handler": "main.handle"},
            },
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
        }
        template = {"Resources": resources}
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=logical_id_translator
        )
        self.resources = resources
        self.resolver = IntrinsicResolver(
            template=template, symbol_resolver=symbol_resolver
        )

    def test_fn_getatt_basic_translation(self):
        intrinsic = {"Fn::GetAtt": ["RestApi", "RootResourceId"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(result, "/")

    def test_fn_getatt_logical_id_translated(self):
        intrinsic = {"Fn::GetAtt": ["LambdaFunction", "Arn"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
            "-1:123456789012:LambdaFunction/invocations",
        )

    def test_fn_getatt_with_fn_join(self):
        intrinsic = self.resources.get("LambdaFunction").get("Properties").get("Uri")
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us"
            "-east-1:406033500479:function:HelloHandler2E4FBA4D/invocations",
        )

    @parameterized.expand(
        [
            (
                    "Fn::GetAtt must fail if the argument does not resolve to a list: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, "test", 42, None]
        ]
    )
    def test_fn_getatt_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::GetAtt should fail if it doesn't have exactly 2 arguments: {}".format(
                        item
                    ),
                    item,
            )
            for item in [[""] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_getatt_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::GetAtt": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::GetAtt first argument must resolve to a valid string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, [], 42, None]
        ]
    )
    def test_fn_getatt_first_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::GetAtt": [intrinsic, IntrinsicResolver.REF]}
            )

    @parameterized.expand(
        [
            (
                    "Fn::GetAtt second argument must resolve to a string:{}".format(item),
                    item,
            )
            for item in [True, False, {}, [], 42, None]
        ]
    )
    def test_fn_getatt_second_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::GetAtt": ["some logical Id", intrinsic]}
            )


class TestIntrinsicFnSubResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "123456789012",
        }
        resources = {
            "LambdaFunction": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {"Uri": "test"},
            }
        }
        template = {"Resources": resources}
        self.resolver = IntrinsicResolver(
            template=template,
            symbol_resolver=IntrinsicsSymbolTable(
                logical_id_translator=logical_id_translator, template=template
            )
        )

    def test_fn_sub_basic_uri(self):
        intrinsic = {
            "Fn::Sub":
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaFunction.Arn}/invocations"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
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
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEqual(
            result,
            "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
            "-1:123456789012:function:LambdaFunction/invocations",
        )

    @parameterized.expand(
        [
            (
                    "Fn::Sub arguments must either resolve to a string or a list".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_sub_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": intrinsic})

    @parameterized.expand(
        [
            (
                    "If Fn::Sub is a list, first argument must resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None]
        ]
    )
    def test_fn_sub_first_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": [intrinsic, {}]})

    @parameterized.expand(
        [
            (
                    "If Fn::Sub is a list, second argument must resolve to a dictionary".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, "Another str", [], 42, None]
        ]
    )
    def test_fn_sub_second_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Sub": ["some str", intrinsic]}
            )

    @parameterized.expand(
        [
            ("If Fn::Sub is a list, it should only have 2 arguments".format(item), item)
            for item in [[""] * i for i in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_sub_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Sub": ["test"] + intrinsic})


class TestIntrinsicFnImportValueResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(template={}, symbol_resolver=IntrinsicsSymbolTable())

    def test_fn_import_value_unsupported(self):
        with self.assertRaises(
                InvalidIntrinsicException, msg="Fn::ImportValue should be unsupported"
        ):
            self.resolver.intrinsic_property_resolver({"Fn::ImportValue": ""})


class TestIntrinsicFnEqualsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012",
        }
        self.resolver = IntrinsicResolver(
            template={},
            symbol_resolver=IntrinsicsSymbolTable(
                logical_id_translator=logical_id_translator
            )
        )

    def test_fn_equals_basic_true(self):
        intrinsic = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_equals_basic_false(self):
        intrinsic = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "NotProd"]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_equals_nested_true(self):
        intrinsic_base_1 = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base_2 = {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}

        intrinsic = {"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_equals_nested_false(self):
        intrinsic_base_1 = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base_2 = {
            "Fn::Equals": [{"Ref": "AWS::AccountId"}, "NOT_A_VALID_ACCOUNT_ID"]
        }

        intrinsic = {"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand(
        [
            (
                    "Fn::Equals must have arguments that resolve to a string: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_equals_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Equals": intrinsic})

    @parameterized.expand(
        [
            ("Fn::Equals must have exactly two arguments: {}".format(item), item)
            for item in [["t"] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_equals_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Equals": intrinsic})


class TestIntrinsicFnNotResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012",
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=logical_id_translator
        )
        self.resolver = IntrinsicResolver(
            template=template, symbol_resolver=symbol_resolver
        )

    def test_fn_not_basic_false(self):
        intrinsic = {"Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_not_basic_true(self):
        intrinsic = {
            "Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "NotProd"]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_not_nested_true(self):
        intrinsic_base_1 = {
            "Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]
        }
        intrinsic_base_2 = {"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}
        # !(True && True)
        intrinsic = {"Fn::Not": [{"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_not_nested_false(self):
        intrinsic_base_1 = {
            "Fn::Not": [{"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}]
        }
        intrinsic_base_2 = {
            "Fn::Not": [{"Fn::Equals": [{"Ref": "AWS::AccountId"}, "123456789012"]}]
        }

        intrinsic = {"Fn::Not": [{"Fn::Equals": [intrinsic_base_1, intrinsic_base_2]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_not_condition_false(self):
        intrinsic = {"Fn::Not": [{"Condition": "TestCondition"}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_not_condition_true(self):
        intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    @parameterized.expand(
        [
            (
                    "Fn::Not must have an argument that resolves to a list: {}".format(
                        item
                    ),
                    item,
            )
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_not_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::Not items in the list must resolve to booleans: {}".format(item),
                    item,
            )
            for item in [{}, 42, None, "test"]
        ]
    )
    def test_fn_not_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": [intrinsic]})

    @parameterized.expand(
        [
            ("Fn::Not must have exactly 1 argument: {}".format(item), item)
            for item in [[True] * i for i in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_not_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Not": intrinsic})

    def test_fn_not_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Not": [{"Condition": "NOT_VALID_CONDITION"}]}
            )


class TestIntrinsicFnAndResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012",
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=logical_id_translator
        )
        self.resolver = IntrinsicResolver(
            template=template, symbol_resolver=symbol_resolver
        )

    def test_fn_and_basic_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {
            "Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_and_basic_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {
            "Fn::And": [
                prod_fn_equals,
                {"Condition": "NotTestCondition"},
                prod_fn_equals,
            ]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_and_nested_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic_base = {
            "Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        fn_not_intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        intrinsic = {"Fn::And": [intrinsic_base, fn_not_intrinsic, prod_fn_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_and_nested_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        prod_fn_not_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "NOT_EQUAL"]}
        intrinsic_base = {
            "Fn::And": [
                prod_fn_equals,
                {"Condition": "NotTestCondition"},
                prod_fn_equals,
            ]
        }
        intrinsic = {"Fn::And": [{"Fn::Not": [intrinsic_base]}, prod_fn_not_equals]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::And must have value that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_and_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::And": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn:And must have all arguments that resolves to booleans".format(item),
                    item,
            )
            for item in [{}, 42, None, "test"]
        ]
    )
    def test_fn_and_all_arguments_bool(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::And": [intrinsic, intrinsic, intrinsic]}
            )

    def test_fn_and_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver(
                {"Fn::And": [{"Condition": "NOT_VALID_CONDITION"}]}
            )


class TestIntrinsicFnOrResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012",
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
        }

        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=logical_id_translator
        )
        self.resolver = IntrinsicResolver(
            template=template, symbol_resolver=symbol_resolver
        )

    def test_fn_or_basic_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_or_basic_single_true(self):
        intrinsic = {"Fn::Or": [False, False, {"Condition": "TestCondition"}, False]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_or_basic_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        intrinsic = {
            "Fn::Or": [
                {"Fn::Not": [prod_fn_equals]},
                {"Condition": "NotTestCondition"},
                {"Fn::Not": [prod_fn_equals]},
            ]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_or_nested_true(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        failed_intrinsic_or = {
            "Fn::Or": [
                {"Fn::Not": [prod_fn_equals]},
                {"Condition": "NotTestCondition"},
                {"Fn::Not": [prod_fn_equals]},
            ]
        }
        intrinsic_base = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        fn_not_intrinsic = {"Fn::Not": [{"Condition": "NotTestCondition"}]}
        intrinsic = {
            "Fn::Or": [
                failed_intrinsic_or,
                intrinsic_base,
                fn_not_intrinsic,
                fn_not_intrinsic,
            ]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_or_nested_false(self):
        prod_fn_equals = {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]}
        failed_intrinsic_or = {
            "Fn::Or": [
                {"Fn::Not": [prod_fn_equals]},
                {"Condition": "NotTestCondition"},
                {"Fn::Not": [prod_fn_equals]},
            ]
        }
        intrinsic_base = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        intrinsic = {"Fn::Or": [failed_intrinsic_or, {"Fn::Not": [intrinsic_base]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand(
        [
            (
                    "Fn::Or must have an argument that resolves to a list: {}".format(item),
                    item,
            )
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_or_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::Or": intrinsic})

    @parameterized.expand(
        [
            (
                    "Fn::Or must have all arguments resolve to booleans: {}".format(item),
                    item,
            )
            for item in [{}, 42, None, "test"]
        ]
    )
    def test_fn_or_all_arguments_bool(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Or": [intrinsic, intrinsic, intrinsic]}
            )

    def test_fn_or_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Or": [{"Condition": "NOT_VALID_CONDITION"}]}
            )


class TestIntrinsicFnIfResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012",
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [{"Ref": "EnvironmentType"}, "prod"]},
            "NotTestCondition": {"Fn::Not": [{"Condition": "TestCondition"}]},
            "InvalidCondition": ["random items"],
        }
        template = {"Conditions": conditions}
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=logical_id_translator
        )
        self.resolver = IntrinsicResolver(
            template=template, symbol_resolver=symbol_resolver
        )

    def test_fn_if_basic_true(self):
        intrinsic = {"Fn::If": ["TestCondition", True, False]}

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_fn_if_basic_false(self):
        intrinsic = {"Fn::If": ["NotTestCondition", True, False]}

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_nested_fn_if_true(self):
        intrinsic_base_1 = {"Fn::If": ["NotTestCondition", True, False]}
        intrinsic_base_2 = {"Fn::If": ["TestCondition", True, False]}
        intrinsic = {"Fn::If": ["TestCondition", intrinsic_base_2, intrinsic_base_1]}

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_if_false(self):
        intrinsic_base_1 = {"Fn::If": ["NotTestCondition", True, False]}
        intrinsic_base_2 = {"Fn::If": ["TestCondition", True, False]}
        intrinsic = {"Fn::If": ["TestCondition", intrinsic_base_1, intrinsic_base_2]}

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand(
        [
            ("Fn::If must an argument that resolves to a list: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test"]
        ]
    )
    def test_fn_if_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({"Fn::If": intrinsic})

    @parameterized.expand(
        [
            ("Fn::If must have the argument resolve to a string: {}".format(item), item)
            for item in [True, False, {}, 42, None, "test", []]
        ]
    )
    def test_fn_if_condition_arguments_invalid_type(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::If": [intrinsic, True, False]}
            )

    def test_fn_if_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver(
                {"Fn::If": ["NOT_VALID_CONDITION", "test", "test"]}
            )

    @parameterized.expand(
        [
            ("Fn::If must have exactly 3 arguments: {}".format(item), item)
            for item in [[True] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
        ]
    )
    def test_fn_if_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver(
                {"Fn::Not": ["TestCondition"] + intrinsic}
            )

    def test_fn_if_condition_not_bool_fail(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver(
                {"Fn::If": ["InvalidCondition", "test", "test"]}
            )


class TestIntrinsicTemplateResolution(TestCase):
    def setUp(self):
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
            Path(__file__).resolve().parents[0].joinpath('test_data', 'test_intrinsic_template_resolution.json'))
        with open(integration_path) as f:
            template = json.load(f)

        self.template = template
        self.resources = template.get("Resources")
        self.conditions = template.get("Conditions")
        self.mappings = template.get("Mappings")

        symbol_resolver = IntrinsicsSymbolTable(
            template=self.template, logical_id_translator=self.logical_id_translator
        )
        self.resolver = IntrinsicResolver(
            template=self.template, symbol_resolver=symbol_resolver
        )

    def test_basic_template_resolution(self):
        resolved_template = self.resolver.resolve_template(ignore_errors=False)
        expected_resources = {
            "HelloHandler2E4FBA4D": {
                "Properties": {"handler": "main.handle"},
                "Type": "AWS::Lambda::Function",
            },
            "LambdaFunction": {
                "Properties": {
                    "Uri": "arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31/functions/arn:aws"
                           ":lambda:us-east-1:406033500479:function:HelloHandler2E4FBA4D/invocations"
                },
                "Type": "AWS::Lambda::Function",
            },
            "RestApi": {
                "Properties": {
                    "Body": "YTtlO2Y7ZA==",
                    "BodyS3Location": "https://s3location/",
                },
                "Type": "AWS::ApiGateway::RestApi",
            },
            "RestApiResource": {
                "Properties": {
                    "PathPart": "{proxy+}",
                    "RestApiId": "RestApi",
                    "parentId": "/",
                }
            },
        }
        self.assertEqual(resolved_template, expected_resources)

    def test_template_fail_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {
            "Fn::FindInMap": []
        }
        template = {
            "Mappings": self.mappings,
            "Conditions": self.conditions,
            "Resources": resources,
        }
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=self.logical_id_translator
        )
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Find In Map"):
            resolver.resolve_template(ignore_errors=False)

    def test_template_ignore_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {
            "Fn::FindInMap": []
        }
        template = {
            "Mappings": self.mappings,
            "Conditions": self.conditions,
            "Resources": resources,
        }
        symbol_resolver = IntrinsicsSymbolTable(
            template=template, logical_id_translator=self.logical_id_translator
        )
        resolver = IntrinsicResolver(template=template, symbol_resolver=symbol_resolver)
        result = resolver.resolve_template(ignore_errors=True)
        expected_template = {
            "HelloHandler2E4FBA4D": {
                "Properties": {"handler": "main.handle"},
                "Type": "AWS::Lambda::Function",
            },
            "LambdaFunction": {
                "Properties": {
                    "Uri": "arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31"
                           "/functions/arn:aws:lambda:us-east-1:406033500479"
                           ":function:HelloHandler2E4FBA4D/invocations"
                },
                "Type": "AWS::Lambda::Function",
            },
            "RestApi.Deployment": {
                "Properties": {
                    "Body": {
                        "Fn::Base64": {
                            "Fn::Join": [
                                ";",  # NOQA
                                {
                                    "Fn::Split": [
                                        ",",
                                        {"Fn::Join": [",", ["a", "e", "f", "d"]]},
                                    ]
                                },
                            ]
                        }
                    },
                    "BodyS3Location": {"Fn::FindInMap": []},
                },
                "Type": "AWS::ApiGateway::RestApi",
            },
            "RestApiResource": {
                "Properties": {
                    "PathPart": "{proxy+}",
                    "RestApiId": "RestApi",
                    "parentId": "/",
                }
            },
        }
        self.assertEqual(expected_template, result)


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
