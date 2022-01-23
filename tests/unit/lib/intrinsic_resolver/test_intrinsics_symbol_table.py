from unittest import TestCase

from unittest.mock import patch

from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidSymbolException
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestIntrinsicsSymbolTablePseudoProperties(TestCase):
    def setUp(self):
        self.symbol_table = IntrinsicsSymbolTable(template={})

    def test_handle_account_id_default(self):
        self.assertEqual(self.symbol_table.handle_pseudo_account_id(), "123456789012")

    def test_pseudo_partition(self):
        self.assertEqual(self.symbol_table.handle_pseudo_partition(), "aws")

    @patch("samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os")
    def test_pseudo_partition_gov(self, mock_os):
        mock_os.getenv.return_value = "us-west-gov-1"
        self.assertEqual(self.symbol_table.handle_pseudo_partition(), "aws-us-gov")

    @patch("samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os")
    def test_pseudo_partition_china(self, mock_os):
        mock_os.getenv.return_value = "cn-west-1"
        self.assertEqual(self.symbol_table.handle_pseudo_partition(), "aws-cn")

    @patch("samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os")
    def test_pseudo_region_environ(self, mock_os):
        mock_os.getenv.return_value = "mytemp"
        self.assertEqual(self.symbol_table.handle_pseudo_region(), "mytemp")

    @patch("samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os")
    def test_pseudo_default_region(self, mock_os):
        mock_os.getenv.return_value = None
        self.assertEqual(self.symbol_table.handle_pseudo_region(), "us-east-1")

    def test_pseudo_no_value(self):
        self.assertIsNone(self.symbol_table.handle_pseudo_no_value())

    def test_pseudo_url_prefix_default(self):
        self.assertEqual(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com")

    @patch("samcli.lib.intrinsic_resolver.intrinsics_symbol_table.os")
    def test_pseudo_url_prefix_china(self, mock_os):
        mock_os.getenv.return_value = "cn-west-1"
        self.assertEqual(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com.cn")

    def test_get_availability_zone(self):
        res = IntrinsicsSymbolTable.get_availability_zone("us-east-1")
        self.assertIn("us-east-1a", res)

    def test_handle_pseudo_account_id(self):
        res = IntrinsicsSymbolTable.handle_pseudo_account_id()
        self.assertEqual(res, "123456789012")

    def test_handle_pseudo_stack_name(self):
        res = IntrinsicsSymbolTable.handle_pseudo_stack_name()
        self.assertEqual(res, "local")

    def test_handle_pseudo_stack_id(self):
        res = IntrinsicsSymbolTable.handle_pseudo_stack_id()
        self.assertEqual(
            res, "arn:aws:cloudformation:us-east-1:123456789012:stack/" "local/51af3dc0-da77-11e4-872e-1234567db123"
        )


class TestSymbolResolution(TestCase):
    def test_parameter_symbols(self):
        template = {"Resources": {}, "Parameters": {"Test": {"Default": "data"}}}
        symbol_resolver = IntrinsicsSymbolTable(template=template)
        result = symbol_resolver.resolve_symbols("Test", IntrinsicResolver.REF)
        self.assertEqual(result, "data")

    def test_parameter_symbols_for_empty_string(self):
        template = {"Resources": {}, "Parameters": {"Test": {"Default": ""}}}
        symbol_resolver = IntrinsicsSymbolTable(template=template)
        result = symbol_resolver.resolve_symbols("Test", IntrinsicResolver.REF)
        self.assertEqual(result, "")

    def test_default_type_resolver_function(self):
        template = {"Resources": {"MyApi": {"Type": "AWS::ApiGateway::RestApi"}}}
        default_type_resolver = {"AWS::ApiGateway::RestApi": {"RootResourceId": lambda logical_id: logical_id}}

        symbol_resolver = IntrinsicsSymbolTable(template=template, default_type_resolver=default_type_resolver)
        result = symbol_resolver.resolve_symbols("MyApi", "RootResourceId")

        self.assertEqual(result, "MyApi")

    def test_custom_attribute_resolver(self):
        template = {"Resources": {"MyApi": {"Type": "AWS::ApiGateway::RestApi"}}}
        common_attribute_resolver = {"Arn": "test"}

        symbol_resolver = IntrinsicsSymbolTable(template=template, common_attribute_resolver=common_attribute_resolver)
        result = symbol_resolver.resolve_symbols("MyApi", "Arn")

        self.assertEqual(result, "test")

    def test_unknown_symbol_translation(self):
        symbol_resolver = IntrinsicsSymbolTable(template={})
        res = symbol_resolver.get_translation("UNKNOWN MAP")
        self.assertEqual(res, None)

    def test_basic_symbol_translation(self):
        symbol_resolver = IntrinsicsSymbolTable(template={}, logical_id_translator={"item": "test"})
        res = symbol_resolver.get_translation("item")
        self.assertEqual(res, "test")

    def test_basic_unknown_translated_string_translation(self):
        symbol_resolver = IntrinsicsSymbolTable(template={}, logical_id_translator={"item": "test"})
        res = symbol_resolver.get_translation("item", "RootResourceId")
        self.assertEqual(res, None)

    def test_arn_resolver_default_service_name(self):
        res = IntrinsicsSymbolTable().arn_resolver("test")
        self.assertEqual(res, "arn:aws:lambda:us-east-1:123456789012:function:test")

    def test_arn_resolver_lambda(self):
        res = IntrinsicsSymbolTable().arn_resolver("test", service_name="lambda")
        self.assertEqual(res, "arn:aws:lambda:us-east-1:123456789012:function:test")

    def test_arn_resolver_sns(self):
        res = IntrinsicsSymbolTable().arn_resolver("test", service_name="sns")
        self.assertEqual(res, "arn:aws:sns:us-east-1:123456789012:test")

    def test_arn_resolver_lambda_with_function_name(self):
        template = {"Resources": {"LambdaFunction": {"Properties": {"FunctionName": "function-name-override"}}}}
        res = IntrinsicsSymbolTable(template=template).arn_resolver("LambdaFunction", service_name="lambda")
        self.assertEqual(res, "arn:aws:lambda:us-east-1:123456789012:function:function-name-override")

    def test_resolver_ignore_errors(self):
        resolver = IntrinsicsSymbolTable()
        res = resolver.resolve_symbols("UNKNOWN", "SOME UNKNOWN RESOURCE PROPERTY", ignore_errors=True)
        self.assertEqual(res, "$UNKNOWN.SOME UNKNOWN RESOURCE PROPERTY")

    def test_symbol_resolver_unknown_fail(self):
        resolver = IntrinsicsSymbolTable()
        with self.assertRaises(InvalidSymbolException):
            resolver.resolve_symbols("UNKNOWN", "SOME UNKNOWN RESOURCE PROPERTY")
