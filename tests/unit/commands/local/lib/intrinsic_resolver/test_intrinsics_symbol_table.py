from unittest import TestCase

import mock
from mock import patch

from samcli.commands.local.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestIntrinsicsSymbolTableValidAttributes(TestCase):
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
        self.sample_resource_spec = {"AWS::ApiGateway::RestApi": {
            "Attributes": {
                "RootResourceId": {
                    "PrimitiveType": "String"
                }
            },
            "Properties": {
                "ApiKeySourceType": {
                    "PrimitiveType": "String",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "BinaryMediaTypes": {
                    "DuplicatesAllowed": False,
                    "PrimitiveItemType": "String",
                    "Required": False,
                    "Type": "List",
                    "UpdateType": "Mutable"
                },
                "Body": {
                    "PrimitiveType": "Json",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "BodyS3Location": {
                    "Required": False,
                    "Type": "S3Location",
                    "UpdateType": "Mutable"
                },
                "CloneFrom": {
                    "PrimitiveType": "String",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "Description": {
                    "PrimitiveType": "String",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "EndpointConfiguration": {
                    "Required": False,
                    "Type": "EndpointConfiguration",
                    "UpdateType": "Mutable"
                },
                "FailOnWarnings": {
                    "PrimitiveType": "Boolean",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "MinimumCompressionSize": {
                    "PrimitiveType": "Integer",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "Name": {
                    "PrimitiveType": "String",
                    "Required": False,
                    "UpdateType": "Mutable"
                },
                "Parameters": {
                    "DuplicatesAllowed": False,
                    "PrimitiveItemType": "String",
                    "Required": False,
                    "Type": "Map",
                    "UpdateType": "Mutable"
                },
                "Policy": {
                    "PrimitiveType": "Json",
                    "Required": False,
                    "UpdateType": "Mutable"
                }
            }
        }}
        self.resources = resources
        self.resolver = IntrinsicResolver(
            symbol_resolver=IntrinsicsSymbolTable(logical_id_translator=logical_id_translator, resources=resources))


class TestIntrinsicsSymbolTablePseudoProperties(TestCase):
    def setUp(self):
        self.symbol_table = IntrinsicsSymbolTable()

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.Popen')
    def test_handle_account_id_system(self, mock_subproc_popen):
        process_mock = mock.Mock()
        attrs = {'communicate.return_value': ('12312312312', 0)}
        process_mock.configure_mock(**attrs)
        mock_subproc_popen.return_value = process_mock

        result = self.symbol_table.handle_pseudo_account_id()
        self.assertEquals(result, '12312312312')

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.Popen')
    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.randint')
    def test_handle_account_id_default(self, random_call, mock_subproc_popen):
        random_call.return_value = 1

        process_mock = mock.Mock()
        attrs = {'communicate.return_value': ('', 0)}
        process_mock.configure_mock(**attrs)
        mock_subproc_popen.return_value = process_mock

        result = self.symbol_table.handle_pseudo_account_id()
        self.assertEquals(result, '111111111111')

    def test_pseudo_notification_arns(self):
        pass

    def test_pseudo_partition(self):
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_gov(self, mock_os):
        mock_os.getenv.return_value = 'us-west-gov-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-us-gov")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_partition_china(self, mock_os):
        mock_os.getenv.return_value = 'cn-west-1'
        self.assertEquals(self.symbol_table.handle_pseudo_partition(), "aws-cn")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_region_environ(self, mock_os):
        mock_os.getenv.return_value = "mytemp"
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "mytemp")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_default_region(self, mock_os):
        mock_os.getenv.return_value = None
        self.assertEquals(self.symbol_table.handle_pseudo_region(), "us-east-1")

    def test_pseudo_no_value(self):
        self.assertIsNone(self.symbol_table.handle_pseudo_no_value())

    def test_pseudo_url_prefix_default(self):
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com")

    @patch('samcli.commands.local.lib.intrinsic_resolver.intrinsics_symbol_table.os')
    def test_pseudo_url_prefix_china(self, mock_os):
        mock_os.getenv.return_value = "cn-west-1"
        self.assertEquals(self.symbol_table.handle_pseudo_url_prefix(), "amazonaws.com.cn")
