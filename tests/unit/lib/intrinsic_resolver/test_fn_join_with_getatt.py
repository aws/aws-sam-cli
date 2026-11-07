"""
Unit tests for Fn::Join with Fn::GetAtt bug fix
"""

from unittest import TestCase
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestFnJoinWithGetAtt(TestCase):
    """
    Test that Fn::Join works correctly with Fn::GetAtt for Lambda function ARNs,
    especially when the FunctionName property contains intrinsic functions.
    """

    def test_fn_join_with_getatt_simple_function_name(self):
        """
        Test Fn::Join with Fn::GetAtt when FunctionName is a simple string
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": "my-function-name",
                    },
                }
            }
        }

        resolver = IntrinsicResolver(
            template=template, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator={}, template=template)
        )

        uri_intrinsic = {
            "Fn::Join": [
                "",
                [
                    "arn:",
                    {"Ref": "AWS::Partition"},
                    ":apigateway:",
                    {"Ref": "AWS::Region"},
                    ":lambda:path/2015-03-31/functions/",
                    {"Fn::GetAtt": ["MyFunction", "Arn"]},
                    "/invocations",
                ],
            ]
        }

        result = resolver.intrinsic_property_resolver(uri_intrinsic, ignore_errors=False)

        self.assertIsInstance(result, str)
        self.assertIn("my-function-name", result)
        self.assertIn("arn:aws:apigateway:", result)
        self.assertIn("lambda:path/2015-03-31/functions/", result)
        self.assertIn("/invocations", result)

    def test_fn_join_with_getatt_intrinsic_function_name(self):
        """
        Test Fn::Join with Fn::GetAtt when FunctionName contains Fn::Sub
        This was the original bug - it would throw TypeError: unhashable type: 'dict'
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": {"Fn::Sub": "my-${AWS::StackName}-function"},
                    },
                }
            }
        }

        resolver = IntrinsicResolver(
            template=template, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator={}, template=template)
        )

        uri_intrinsic = {
            "Fn::Join": [
                "",
                [
                    "arn:",
                    {"Ref": "AWS::Partition"},
                    ":apigateway:",
                    {"Ref": "AWS::Region"},
                    ":lambda:path/2015-03-31/functions/",
                    {"Fn::GetAtt": ["MyFunction", "Arn"]},
                    "/invocations",
                ],
            ]
        }

        result = resolver.intrinsic_property_resolver(uri_intrinsic, ignore_errors=False)

        self.assertIsInstance(result, str)
        self.assertIn("MyFunction", result)
        self.assertIn("arn:aws:apigateway:", result)
        self.assertIn("lambda:path/2015-03-31/functions/", result)
        self.assertIn("/invocations", result)

    def test_fn_join_with_getatt_no_function_name(self):
        """
        Test Fn::Join with Fn::GetAtt when FunctionName property is not defined
        Should use the logical ID as the function name
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                }
            }
        }

        resolver = IntrinsicResolver(
            template=template, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator={}, template=template)
        )

        uri_intrinsic = {
            "Fn::Join": [
                "",
                [
                    "arn:",
                    {"Ref": "AWS::Partition"},
                    ":apigateway:",
                    {"Ref": "AWS::Region"},
                    ":lambda:path/2015-03-31/functions/",
                    {"Fn::GetAtt": ["MyFunction", "Arn"]},
                    "/invocations",
                ],
            ]
        }

        result = resolver.intrinsic_property_resolver(uri_intrinsic, ignore_errors=False)

        self.assertIsInstance(result, str)
        self.assertIn("MyFunction", result)
        self.assertIn("arn:aws:apigateway:", result)
        self.assertIn("lambda:path/2015-03-31/functions/", result)
        self.assertIn("/invocations", result)

    def test_fn_sub_still_works_with_getatt(self):
        """
        Ensure that the fix doesn't break Fn::Sub with Fn::GetAtt (which was already working)
        """
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "FunctionName": {"Fn::Sub": "my-${AWS::StackName}-function"},
                    },
                }
            }
        }

        resolver = IntrinsicResolver(
            template=template, symbol_resolver=IntrinsicsSymbolTable(logical_id_translator={}, template=template)
        )

        uri_intrinsic = {
            "Fn::Sub": "arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${MyFunction.Arn}/invocations"
        }

        result = resolver.intrinsic_property_resolver(uri_intrinsic, ignore_errors=False)

        self.assertIsInstance(result, str)
        self.assertIn("MyFunction", result)
        self.assertIn("arn:aws:apigateway:", result)
        self.assertIn("lambda:path/2015-03-31/functions/", result)
        self.assertIn("/invocations", result)
