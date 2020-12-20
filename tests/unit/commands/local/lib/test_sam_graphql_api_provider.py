import json
import tempfile
from collections import OrderedDict
from unittest import TestCase

from os import path
from unittest.mock import patch
from parameterized import parameterized

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.providers.graphql_api_provider import GraphQLApiProvider
from samcli.lib.providers.provider import Cors
from samcli.local.appsync.local_appsync_service import Resolver


class TestSamGraphQLApiProvider(TestCase):
    def setUp(self):
        self.cwd = "/some/working/dir"

    def test_provider_with_no_resource_properties(self):
        template = {"Resources": {"SamFunc1": {"Type": "AWS::Lambda::Function"}}}

        provider = GraphQLApiProvider(template)

        self.assertEqual(provider.resolvers, [])
        self.assertEqual(provider.api.resolvers, [])

    def test_provider_with_correct_schema(self):
        example_schema_path = "schema_path/schema_file_name.gql"
        template = {
            "Resources": {
                "SamSchema1": {
                    "Type": "AWS::AppSync::GraphQLSchema",
                    "Properties": {
                        "ApiId": "SomeApiId",
                        "DefinitionS3Location": example_schema_path,
                    },
                }
            }
        }

        provider = GraphQLApiProvider(template, cwd=self.cwd)

        self.assertEqual(provider.api.schema_path, path.join(self.cwd, example_schema_path))

    # @parameterized.expand([
    #     ("AWS::Serverless::Function"), ("AWS::Lambda::Function")
    # ])
    def test_provider_with_single_resolver(self, lambda_function_resource_type="AWS::Serverless::Function"):
        lambda_function_name = "FoorBarName"
        resolver_type_name = "Query"
        resolver_field_name = "blueYellowFieldName"
        data_source_name = "SamDataSource1"

        template = {
            "Resources": {
                "SamResolver1": {
                    "Type": "AWS::AppSync::Resolver",
                    "Properties": {
                        "ApiId": "SomeApiId",
                        "TypeName": resolver_type_name,
                        "FieldName": resolver_field_name,
                        "DataSourceName": {"Fn::GetAtt": [data_source_name, "Name"]},
                    },
                },
                data_source_name: {
                    "Type": "AWS::AppSync::DataSource",
                    "Properties": {
                        "ApiId": "SomeApiId",
                        "LambdaConfig": {"LambdaFunctionArn": {"Fn::GetAtt": [lambda_function_name, "Arn"]}},
                        "Type": "AWS_LAMBDA",
                    },
                },
                lambda_function_name: {
                    "Type": lambda_function_resource_type,
                    "Properties": {},
                },
            }
        }

        provider = GraphQLApiProvider(template, cwd=self.cwd)
        api = provider.api
        print("Provider", api.resolvers)

        self.assertEqual(len(provider.api.resolvers), 1)
        self.assertEqual(
            provider.api.resolvers[0],
            Resolver(
                lambda_function_name,
                resolver_type_name,
                resolver_field_name,
            ),
        )
