from copy import deepcopy
from unittest import TestCase

import mock
from parameterized import parameterized

from samcli.commands.local.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.commands.local.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException


class TestIntrinsicFnJoinResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_join(self):
        intrinsic = {
            "Fn::Join": [",", ["a", "b", "c", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "a,b,c,d")

    def test_nested_fn_join(self):
        intrinsic_base_1 = {
            "Fn::Join": [",", ["a", "b", "c", "d"]]
        }
        intrinsic_base_2 = {
            "Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]
        }
        intrinsic = {
            "Fn::Join": [":", [intrinsic_base_1, "e", "f", intrinsic_base_2]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "a,b,c,d:e:f:g;h;i;a,b,c,d")

    def test_delimiter_fn_join(self):
        intrinsic_base_1 = {
            "Fn::Join": ["", ["t", "e", "s", "t"]]
        }
        intrinsic = {
            "Fn::Join": [intrinsic_base_1, ["a", "e", "f", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "atestetestftestd")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object, None]
    ])
    def test_fn_join_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_join_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": [delimiter, []]
            })

    @parameterized.expand([
        ("Invalid Types to the listOfObjects for Fn::Join with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, "t", None]
    ])
    def test_fn_list_of_objects_invalid_type(self, name, list_of_objects):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": ["", list_of_objects]
            })

    @parameterized.expand([
        ("Invalid Types to the listOfObjects for Fn::Join with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_join_items_all_str(self, name, single_obj):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": ["", ["test", single_obj, "abcd"]]
            })


class TestIntrinsicFnSplitResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {
            "Fn::Split": ["|", "a|b|c"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ["a", "b", "c"])

    def test_nested_fn_split(self):
        intrinsic_base_1 = {
            "Fn::Split": [";", {"Fn::Join": [";", ["a", "b", "c"]]}]
        }

        intrinsic_base_2 = {
            "Fn::Join": [",", intrinsic_base_1]
        }
        intrinsic = {
            "Fn::Split": [",", {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ['a', 'b', 'c', '', 'e', '', 'f', '', 'a', 'b', 'c'])

    def test_delimiter_fn_split(self):
        intrinsic_base_1 = {
            "Fn::Join": ["", [","]]
        }
        intrinsic = {
            "Fn::Split": [intrinsic_base_1, {"Fn::Join": [",", ["a", "e", "f", "d"]]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ['a', 'e', 'f', 'd'])

    @parameterized.expand([
        ("Invalid Types to the argument of Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object]
    ])
    def test_fn_split_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first argument of Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object]
    ])
    def test_fn_split_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": [delimiter, []]
            })

    @parameterized.expand([
        ("Invalid Types to the source_string for Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object]
    ])
    def test_fn_split_source_string_invalid_type(self, name, source_string):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": ["", source_string]
            })


class TestIntrinsicFnBase64Resolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_split(self):
        intrinsic = {
            "Fn::Base64": "AWS CloudFormation"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, 'QVdTIENsb3VkRm9ybWF0aW9u')

    def test_nested_fn_base64(self):
        intrinsic_base_1 = {
            "Fn::Base64": "AWS CloudFormation"
        }

        intrinsic_base_2 = {
            "Fn::Base64": intrinsic_base_1
        }
        intrinsic = {
            "Fn::Base64": {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "VVZaa1ZFbEZUbk5pTTFaclVtMDVlV0pYUmpCaFZ6bDEsLGUsLGYsLFVWWmtWRWxGVG5OaU0xWnJ"
                                  "VbTA1ZVdKWFJqQmhWemwx")

    @parameterized.expand([
        ("Invalid Types to the argument of Fn::Base64 with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_base64_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Base64": intrinsic
            })


class TestIntrinsicFnSelectResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable())

    def test_basic_fn_select(self):
        intrinsic = {
            "Fn::Select": [2, ["a", "b", "c", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "c")

    def test_nested_fn_select(self):
        intrinsic_base_1 = {
            "Fn::Select": [0, ["a", "b", "c", "d"]]
        }
        intrinsic_base_2 = {
            "Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]
        }
        intrinsic = {
            "Fn::Select": [3, [intrinsic_base_2, "e", "f", intrinsic_base_2]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "g;h;i;a")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object, None]
    ])
    def test_fn_select_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, object, "3", None]
    ])
    def test_fn_select_index_invalid_index_type(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [index, [0]]
            })

    @parameterized.expand([
        ("Invalid Types to the for Fn::Select with type {} should fail".format(number), number)
        for number in
        [-2, 7]
    ])
    def test_fn_select_invalid_index(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [index, []]
            })

    @parameterized.expand([
        ("Invalid Types to the second list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, object, "3", 33, None]
    ])
    def test_fn_select_objects_invalid_type(self, name, argument):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [0, argument]
            })


class TestIntrinsicFnFindInMapResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable(), mappings={
            "Basic": {
                "Test": {
                    "key": "value"
                }
            },
            "value": {
                "anotherkey": {
                    "key": "result"
                }
            },
            "result": {
                "value": {
                    "key": "final"
                }
            }
        })

    def test_basic_find_in_map(self):
        intrinsic = {
            "Fn::FindInMap": ["Basic", "Test", "key"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "value")

    def test_nested_find_in_map(self):
        intrinsic_base_1 = {
            "Fn::FindInMap": ["Basic", "Test", "key"]
        }
        intrinsic_base_2 = {
            "Fn::FindInMap": [intrinsic_base_1, "anotherkey", "key"]
        }
        intrinsic = {
            "Fn::FindInMap": [intrinsic_base_2, intrinsic_base_1, "key"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "final")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object, None]
    ])
    def test_fn_find_in_map_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::FindInMap": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [[""] * i for i in [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_find_in_map_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::FindInMap": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [["<UNKOWN_VALUE>", "Test", "key"], ["Basic", "<UNKOWN_VALUE>", "key"], ["Basic", "Test", "<UNKOWN_VALUE>"]]
    ])
    def test_fn_find_in_map_invalid_key_entries(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::FindInMap": intrinsic
            })


class TestIntrinsicFnAzsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "AWS::Region": "us-east-1"
        }
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator))

    def test_basic_azs(self):
        intrinsic = {
            "Ref": "AWS::Region"
        }
        result = self.resolver.intrinsic_property_resolver({
            "Fn::GetAZs": intrinsic
        })
        self.assertEquals(result, ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"])

    @parameterized.expand([
        ("Invalid Types to the string argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_azs_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::GetAZs": intrinsic
            })


class TestIntrinsicFnRefResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "RestApi": {
                "Ref": "NewRestApi"
            },
            "AWS::StackId": "12301230123"
        }
        resources = {
            "RestApi": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                },
            }
        }

        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, resources=resources))

    def test_basic_ref_translation(self):
        intrinsic = {
            "Ref": "RestApi"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "NewRestApi")

    def test_default_ref_translation(self):
        intrinsic = {
            "Ref": "UnknownApi"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "UnknownApi")

    @parameterized.expand([
        ("Invalid Types to the string argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_ref_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Ref": intrinsic
            })


class TestIntrinsicFnGetAttResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "RestApi": {
                "Ref": "NewRestApi"
            },
            "LambdaFunction": {
                "Arn": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                       "-1:123456789012:LambdaFunction/invocations"
            },
            "AWS::StackId": "12301230123",
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "406033500479"
        }
        resources = {
            "RestApi": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                },
            },
            "HelloHandler2E4FBA4D": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "handler": "main.handle"
                }
            },
            "LambdaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Uri": {
                        "Fn::Join": [
                            "",
                            [
                                "arn:",
                                {
                                    "Ref": "AWS::Partition"
                                },
                                ":apigateway:",
                                {
                                    "Ref": "AWS::Region"
                                },
                                ":lambda:path/2015-03-31/functions/",
                                {
                                    "Fn::GetAtt": [
                                        "HelloHandler2E4FBA4D",
                                        "Arn"
                                    ]
                                },
                                "/invocations"
                            ]
                        ]
                    }
                }
            }
        }
        self.resources = resources
        self.resolver = IntrinsicResolver(resources=resources,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_fn_getatt_translation(self):
        intrinsic = {
            "Fn::GetAtt": ["RestApi", "RootResourceId"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "/")

    def test_logical_id_translated_fn_getatt(self):
        intrinsic = {
            "Fn::GetAtt": ["LambdaFunction", "Arn"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                                  "-1:123456789012:LambdaFunction/invocations")

    def test_fn_join_getatt(self):
        intrinsic = self.resources.get("LambdaFunction").get("Properties").get("Uri")
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us"
                                  "-east-1:406033500479:HelloHandler2E4FBA4D/invocations")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, "test", 42, object, None]
    ])
    def test_fn_getatt_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::GetAtt": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail. Only 2 arguments to Fn::GetAtt will work"
         .format(primitive), primitive)
        for primitive in
        [[""] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_getatt_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::GetAtt": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first argument with type {} if not a string should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, [], 42, object, None]
    ])
    def test_fn_getatt_first_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::GetAtt": [intrinsic, IntrinsicResolver.REF]
            })

    @parameterized.expand([
        ("Invalid Types to the first argument with type {} if not a string should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, [], 42, object, None]
    ])
    def test_fn_getatt_second_arguments_invalid(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::GetAtt": ["some logical Id", intrinsic]
            })


class TestIntrinsicFnSubResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "123456789012"
        }
        resources = {
            "LambdaFunction": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                    "Uri": "test"
                },
            }
        }
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, resources=resources))

    def test_basic_fn_sub_uri(self):
        intrinsic = {
            "Fn::Sub":
                "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${LambdaFunction.Arn}/invocations"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result,
                          "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                          "-1:123456789012:LambdaFunction/invocations")

    def test_argument_fn_sub_uri(self):
        intrinsic = {
            "Fn::Sub":
                ["arn:aws:apigateway:${MyItem}:lambda:path/2015-03-31/functions/${MyOtherItem}/invocations",
                 {"MyItem": {"Ref": "AWS::Region"}, "MyOtherItem": "LambdaFunction.Arn"}]

        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result,
                          "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                          "-1:123456789012:LambdaFunction/invocations")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_sub_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Sub": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_sub_first_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Sub": [intrinsic, {}]
            })

    @parameterized.expand([
        ("Invalid Types to the second argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Another str", [], 42, object, None]
    ])
    def test_fn_sub_second_argument_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Sub": ["some str", intrinsic]
            })

    @parameterized.expand([
        ("Invalid Number of arguments to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [[""] * i for i in [0, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_sub_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Sub": ["test"] + intrinsic
            })


class TestIntrinsicFnImportValueResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver=IntrinsicsSymbolTable())

    def test_fn_import_value_unsupported(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Fn::ImportValue should be unsupported"):
            self.resolver.intrinsic_property_resolver({
                "Fn::ImportValue": ""
            })


class TestIntrinsicFnEqualsResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012"
        }
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator))

    def test_basic_fn_equals_true(self):
        intrinsic = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_basic_fn_equals_false(self):
        intrinsic = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "NotProd"
        ]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_nested_fn_equals_true(self):
        intrinsic_base_1 = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic_base_2 = {"Fn::Equals": [
            {"Ref": "AWS::AccountId"},
            "123456789012"
        ]}

        intrinsic = {"Fn::Equals": [
            intrinsic_base_1,
            intrinsic_base_2
        ]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_equals_false(self):
        intrinsic_base_1 = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic_base_2 = {"Fn::Equals": [
            {"Ref": "AWS::AccountId"},
            "NOT_A_VALID_ACCOUNT_ID"
        ]}

        intrinsic = {"Fn::Equals": [
            intrinsic_base_1,
            intrinsic_base_2
        ]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test"]
    ])
    def test_fn_equals_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Equals": intrinsic
            })

    @parameterized.expand([
        ("Invalid Number of arguments to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [["t"] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_sub_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Equals": intrinsic
            })


class TestIntrinsicFnNotResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012"
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [
                {"Ref": "EnvironmentType"},
                "prod"
            ]},
            "NotTestCondition": {
                "Fn::Not": [
                    {
                        "Condition": "TestCondition"
                    }
                ]
            }
        }
        self.resolver = IntrinsicResolver(conditions=conditions,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_fn_not_false(self):
        intrinsic = {"Fn::Not": [{"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_basic_fn_not_true(self):
        intrinsic = {"Fn::Not": [{"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "NotProd"
        ]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_not_true(self):
        intrinsic_base_1 = {"Fn::Not": [{"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}]}
        intrinsic_base_2 = {"Fn::Equals": [
            {"Ref": "AWS::AccountId"},
            "123456789012"
        ]}
        # !(True && True)
        intrinsic = {"Fn::Not": [{"Fn::Equals": [
            intrinsic_base_1,
            intrinsic_base_2
        ]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_not_false(self):
        intrinsic_base_1 = {"Fn::Not": [{"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}]}
        intrinsic_base_2 = {"Fn::Not": [{"Fn::Equals": [
            {"Ref": "AWS::AccountId"},
            "123456789012"
        ]}]}

        intrinsic = {"Fn::Not": [{"Fn::Equals": [
            intrinsic_base_1,
            intrinsic_base_2
        ]}]}
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_not_condition_false(self):
        intrinsic = {
            "Fn::Not": [{
                "Condition": "TestCondition"
            }]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_fn_not_condition_true(self):
        intrinsic = {
            "Fn::Not": [{
                "Condition": "NotTestCondition"
            }]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test"]
    ])
    def test_fn_not_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Not": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first bool argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [{}, 42, object, None, "test"]
    ])
    def test_fn_not_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Not": [intrinsic]
            })

    @parameterized.expand([
        ("Invalid Number of arguments to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [[True] * i for i in [0, 3, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_not_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Not": intrinsic
            })

    def test_fn_not_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({
                "Fn::Not": [{"Condition": "NOT_VALID_CONDITION"}]
            })


class TestIntrinsicFnAndResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012"
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [
                {"Ref": "EnvironmentType"},
                "prod"
            ]},
            "NotTestCondition": {
                "Fn::Not": [
                    {
                        "Condition": "TestCondition"
                    }
                ]
            }
        }
        self.resolver = IntrinsicResolver(conditions=conditions,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_fn_and_true(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic = {
            "Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_basic_fn_and_false(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic = {
            "Fn::And": [prod_fn_equals, {"Condition": "NotTestCondition"}, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_nested_fn_and_true(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic_base = {
            "Fn::And": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        fn_not_intrinsic = {"Fn::Not": [{
            "Condition": "NotTestCondition"
        }]}
        intrinsic = {
            "Fn::And": [intrinsic_base, fn_not_intrinsic, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_and_false(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        prod_fn_not_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "NOT_EQUAL"
        ]}
        intrinsic_base = {
            "Fn::And": [prod_fn_equals, {"Condition": "NotTestCondition"}, prod_fn_equals]
        }
        intrinsic = {
            "Fn::And": [{"Fn::Not": [intrinsic_base]}, prod_fn_not_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test"]
    ])
    def test_fn_and_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::And": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first bool argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [{}, 42, object, None, "test"]
    ])
    def test_fn_and_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::And": [intrinsic, intrinsic, intrinsic]
            })

    def test_fn_and_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({
                "Fn::And": [{"Condition": "NOT_VALID_CONDITION"}]
            })


class TestIntrinsicFnOrResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012"
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [
                {"Ref": "EnvironmentType"},
                "prod"
            ]},
            "NotTestCondition": {
                "Fn::Not": [
                    {
                        "Condition": "TestCondition"
                    }
                ]
            }
        }
        self.resolver = IntrinsicResolver(conditions=conditions,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_fn_or_true(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_basic_fn_or_single_true(self):
        intrinsic = {
            "Fn::Or": [False, False, {"Condition": "TestCondition"}, False]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_basic_fn_or_false(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        intrinsic = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_nested_fn_or_true(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        failed_intrinsic_or = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        intrinsic_base = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        fn_not_intrinsic = {"Fn::Not": [{
            "Condition": "NotTestCondition"
        }]}
        intrinsic = {
            "Fn::Or": [failed_intrinsic_or, intrinsic_base, fn_not_intrinsic, fn_not_intrinsic]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_and_false(self):
        prod_fn_equals = {"Fn::Equals": [
            {"Ref": "EnvironmentType"},
            "prod"
        ]}
        failed_intrinsic_or = {
            "Fn::Or": [{"Fn::Not": [prod_fn_equals]}, {"Condition": "NotTestCondition"}, {"Fn::Not": [prod_fn_equals]}]
        }
        intrinsic_base = {
            "Fn::Or": [prod_fn_equals, {"Condition": "TestCondition"}, prod_fn_equals]
        }
        intrinsic = {
            "Fn::Or": [failed_intrinsic_or, {"Fn::Not": [intrinsic_base]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test"]
    ])
    def test_fn_or_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Or": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first bool argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [{}, 42, object, None, "test"]
    ])
    def test_fn_or_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Or": [intrinsic, intrinsic, intrinsic]
            })

    def test_fn_or_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({
                "Fn::Or": [{"Condition": "NOT_VALID_CONDITION"}]
            })


class TestIntrinsicFnIfResolver(TestCase):
    def setUp(self):
        logical_id_translator = {
            "EnvironmentType": "prod",
            "AWS::AccountId": "123456789012"
        }
        conditions = {
            "TestCondition": {"Fn::Equals": [
                {"Ref": "EnvironmentType"},
                "prod"
            ]},
            "NotTestCondition": {
                "Fn::Not": [
                    {
                        "Condition": "TestCondition"
                    }
                ]
            },
            "InvalidCondition": ["random items"]
        }
        self.resolver = IntrinsicResolver(conditions=conditions,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_fn_or_true(self):
        intrinsic = {
            "Fn::If": [
                "TestCondition",
                True,
                False
            ]
        }

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_basic_fn_or_false(self):
        intrinsic = {
            "Fn::If": [
                "NotTestCondition",
                True,
                False
            ]
        }

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    def test_nested_fn_if_true(self):
        intrinsic_base_1 = {
            "Fn::If": [
                "NotTestCondition",
                True,
                False
            ]
        }
        intrinsic_base_2 = {
            "Fn::If": [
                "TestCondition",
                True,
                False
            ]
        }
        intrinsic = {
            "Fn::If": [
                "TestCondition",
                intrinsic_base_2,
                intrinsic_base_1
            ]
        }

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertTrue(result)

    def test_nested_fn_if_false(self):
        intrinsic_base_1 = {
            "Fn::If": [
                "NotTestCondition",
                True,
                False
            ]
        }
        intrinsic_base_2 = {
            "Fn::If": [
                "TestCondition",
                True,
                False
            ]
        }
        intrinsic = {
            "Fn::If": [
                "TestCondition",
                intrinsic_base_1,
                intrinsic_base_2
            ]
        }

        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertFalse(result)

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test"]
    ])
    def test_fn_if_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::If": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None, "test", []]
    ])
    def test_fn_if_first_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::If": [intrinsic, True, False]
            })

    def test_fn_if_invalid_condition(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({
                "Fn::If": ["NOT_VALID_CONDITION", "test", "test"]
            })

    @parameterized.expand([
        ("Invalid Number of arguments to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [[True] * i for i in [0, 1, 3, 4, 5, 6, 7, 8, 9, 10]]
    ])
    def test_fn_if_invalid_number_arguments(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Not": ["TestCondition"] + intrinsic
            })

    def test_fn_if_condition_not_bool_fail(self):
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Condition"):
            self.resolver.intrinsic_property_resolver({
                "Fn::If": ["InvalidCondition", "test", "test"]
            })


class TestIntrinsicTemplateResolution(TestCase):
    def setUp(self):
        logical_id_translator = {
            "RestApi": {
                "Ref": "NewRestApi"
            },
            "LambdaFunction": {
                "Arn": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east"
                       "-1:123456789012:LambdaFunction/invocations"
            },
            "AWS::StackId": "12301230123",
            "AWS::Region": "us-east-1",
            "AWS::AccountId": "406033500479",
            "RestApi.Deployment": {
                "Ref": "RestApi"
            }
        }
        self.logical_id_translator = logical_id_translator
        mappings = {
            "TopLevel": {
                "SecondLevelKey": {
                    "key": "https://s3location/"
                }
            }
        }
        resources = {
            "RestApi.Deployment": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                    "Body":
                        {"Fn::Base64":  # Becomes a;e;f;d
                             {"Fn::Join": [";",  # NOQA
                                           {"Fn::Split": [
                                               {"Fn::Select": [1, [";", ","]]},
                                               {"Fn::Join": [",", ["a", "e", "f", "d"]]}]}
                                           ]
                              }
                         },
                    "BodyS3Location": {
                        "Fn::FindInMap": ["TopLevel", "SecondLevelKey", "key"]
                    }
                },
            },
            "RestApiResource": {
                "Properties": {
                    "parentId": {
                        "Fn::GetAtt": [
                            "RestApi.Deployment", "RootResourceId"
                        ]
                    },
                    "PathPart": "{proxy+}",
                    "RestApiId": {
                        "Ref": "RestApi.Deployment"
                    },
                }
            },
            "HelloHandler2E4FBA4D": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "handler": "main.handle"
                }
            },
            "LambdaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Uri": {
                        "Fn::Join": [
                            "",
                            [
                                "arn:",
                                {
                                    "Ref": "AWS::Partition"
                                },
                                ":apigateway:",
                                {
                                    "Fn::Select": [0,
                                                   {
                                                       "Fn::GetAZs": {
                                                           "Ref": "AWS::Region"
                                                       }
                                                   }]
                                },
                                ":lambda:path/2015-03-31/functions/",
                                {
                                    "Fn::GetAtt": [
                                        "HelloHandler2E4FBA4D",
                                        "Arn"
                                    ]
                                },
                                "/invocations"
                            ]
                        ]
                    }
                }
            }
        }
        conditions = {
            "ComplexCondition": {"Fn::And": [
                {"Fn::Equals": [
                    {"Fn::Or":  # NOQA
                        [
                            {"Condition": "NotTestCondition"},
                            {"Condition": "TestCondition"}]
                    }, False]
                },
                True,
                {"Fn::If": ["TestCondition", True, False]}
            ]},
            "TestCondition": {"Fn::Equals": [
                {"Ref": "EnvironmentType"},
                "prod"
            ]},
            "NotTestCondition": {
                "Fn::Not": [
                    {
                        "Condition": "TestCondition"
                    }
                ]
            },
            "InvalidCondition": ["random items"]
        }
        template = {
            "Mappings": mappings,
            "Conditions": conditions,
            "Resources": resources,
        }
        self.resources = resources
        self.conditions = conditions
        self.mappings = mappings
        self.resolver = IntrinsicResolver(template=template,
                                          symbol_resolver=IntrinsicsSymbolTable(
                                              logical_id_translator=logical_id_translator))

    def test_basic_template_resolution(self):
        resolved_template = self.resolver.resolve_template(ignore_errors=False)
        expected_resources = {'HelloHandler2E4FBA4D': {'Properties': {'handler': 'main.handle'},
                                                       'Type': 'AWS::Lambda::Function'},
                              'LambdaFunction': {'Properties': {
                                  'Uri': 'arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31/functions/arn:aws'
                                         ':lambda:us-east-1:406033500479:HelloHandler2E4FBA4D/invocations'},
                                  'Type': 'AWS::Lambda::Function'},
                              'RestApi': {'Properties': {'Body': 'YTtlO2Y7ZA==',
                                                         'BodyS3Location': 'https://s3location/'},
                                          'Type': 'AWS::ApiGateway::RestApi'},
                              'RestApiResource': {'Properties': {'PathPart': '{proxy+}',
                                                                 'RestApiId': 'RestApi',
                                                                 'parentId': '/'}}}
        self.assertEquals(resolved_template, expected_resources)

    def test_template_fail_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {"Fn::FindInMap": []}
        template = {
            "Mappings": self.mappings,
            "Conditions": self.conditions,
            "Resources": resources,
        }

        resolver = IntrinsicResolver(template=template,
                                     symbol_resolver=IntrinsicsSymbolTable(
                                         logical_id_translator=self.logical_id_translator))
        with self.assertRaises(InvalidIntrinsicException, msg="Invalid Find In Map"):
            resolver.resolve_template(ignore_errors=False)

    def test_template_ignore_errors(self):
        resources = deepcopy(self.resources)
        resources["RestApi.Deployment"]["Properties"]["BodyS3Location"] = {"Fn::FindInMap": []}
        template = {
            "Mappings": self.mappings,
            "Conditions": self.conditions,
            "Resources": resources,
        }

        resolver = IntrinsicResolver(template=template,
                                     symbol_resolver=IntrinsicsSymbolTable(
                                         logical_id_translator=self.logical_id_translator))
        result = resolver.resolve_template(ignore_errors=True)
        expected_template = {'HelloHandler2E4FBA4D': {'Properties': {'handler': 'main.handle'},
                                                      'Type': 'AWS::Lambda::Function'},
                             'LambdaFunction': {'Properties': {
                                 'Uri': 'arn:aws:apigateway:us-east-1a:lambda:path/2015-03-31'
                                        '/functions/arn:aws:lambda:us-east-1:406033500479'
                                        ':HelloHandler2E4FBA4D/invocations'},
                                 'Type': 'AWS::Lambda::Function'},
                             'RestApi.Deployment': {
                                 'Properties': {'Body': {'Fn::Base64':
                                                             {'Fn::Join': [';',  # NOQA
                                                                           {'Fn::Split': [{
                                                                               'Fn::Select': [
                                                                                   1,
                                                                                   [
                                                                                       ';',
                                                                                       ',']]},
                                                                               {
                                                                                   'Fn::Join': [
                                                                                       ',',
                                                                                       ['a',
                                                                                        'e',
                                                                                        'f',
                                                                                        'd']]}]}]}},
                                                'BodyS3Location': {'Fn::FindInMap': []}},
                                 'Type': 'AWS::ApiGateway::RestApi'},
                             'RestApiResource': {'Properties': {'PathPart': '{proxy+}',
                                                                'RestApiId': 'RestApi',
                                                                'parentId': '/'}}}
        self.assertEquals(expected_template, result)
