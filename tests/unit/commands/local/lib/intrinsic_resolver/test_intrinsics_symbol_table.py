from unittest import TestCase

from mock import patch, MagicMock

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

    def test_valid_attributes_correct_attribute(self):
        p1 = patch("builtins.open", MagicMock())

        m = MagicMock(side_effect=[self.sample_resource_spec])
        p2 = patch("json.load", m)

        with p1 as _:
            with p2 as _:
                result = self.resolver.symbol_resolver.verify_valid_fn_get_attribute(logical_id="RestApi",
                                                                                     resource_type="RootResourceId")
                self.assertEquals(result, True)

    def test_valid_attributes_incorrect_attribute(self):
        p1 = patch("builtins.open", MagicMock())

        m = MagicMock(side_effect=[self.sample_resource_spec])
        p2 = patch("json.load", m)

        with p1 as _:
            with p2 as _:
                result = self.resolver.symbol_resolver.verify_valid_fn_get_attribute(logical_id="RestApi",
                                                                                     resource_type="UNKNOWN_PROPERTY")
                self.assertEquals(result, False)


class TestIntrinsicsSymbolTablePseudoProperties(TestCase):
    pass
