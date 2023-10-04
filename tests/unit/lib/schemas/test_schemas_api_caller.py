import io
import tempfile


from unittest.mock import Mock
from unittest import TestCase

import botocore
from botocore.exceptions import WaiterError, ClientError

from samcli.lib.schemas.schemas_constants import DEFAULT_EVENT_SOURCE, DEFAULT_EVENT_DETAIL_TYPE
from samcli.commands.exceptions import SchemasApiException
from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound, NotAvailableInRegion
from samcli.commands.remote.exceptions import DuplicateEventName
from samcli.lib.schemas.schemas_api_caller import SchemasApiCaller


class TestSchemasCommand(TestCase):
    def setUp(self):
        self.client = Mock()

    def test_list_registries_with_next_token(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = [
            {
                "ResponseMetadata": {
                    "RequestId": "26f73117-024e-49ce-8788-ea4d9278fdd8",
                    "HTTPStatusCode": 200,
                    "HTTPHeaders": {},
                    "RetryAttempts": 0,
                },
                "NextToken": "1111111111",
                "Registries": [{"RegistryName": "aws.events"}],
            }
        ]

        list_registries_response = schemas_api_caller.list_registries("next_token", max_items)
        self.assertEqual(list_registries_response["registries"], ["aws.events"])
        self.assertEqual(list_registries_response["next_token"], "1111111111")

        self.client.get_paginator.assert_called_once()
        self.client.get_paginator.assert_called_once_with("list_registries")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            PaginationConfig={"StartingToken": "next_token", "MaxItems": max_items, "PageSize": max_items}
        )

    def test_list_registries_without_next_token(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = [
            {
                "ResponseMetadata": {
                    "RequestId": "26f73117-024e-49ce-8788-ea4d9278fdd8",
                    "HTTPStatusCode": 200,
                    "HTTPHeaders": {},
                    "RetryAttempts": 0,
                },
                "Registries": [{"RegistryName": "aws.events"}],
            }
        ]

        list_registries_response = schemas_api_caller.list_registries(None, max_items)
        self.assertEqual(list_registries_response["registries"], ["aws.events"])
        self.assertEqual(list_registries_response["next_token"], None)

        self.client.get_paginator.assert_called_once()
        self.client.get_paginator.assert_called_once_with("list_registries")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            PaginationConfig={"StartingToken": None, "MaxItems": max_items, "PageSize": max_items}
        )

    def test_list_registries_raises_not_available_in_region_exception(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = False
        self.client.get_paginator.return_value.paginate.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.list_registries("next_token", max_items)
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_list_schemas_with_next_token(self):
        registry_name = "registry1"
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = [
            {
                "ResponseMetadata": {
                    "RequestId": "123",
                    "HTTPHeaders": {
                        "x-amzn-requestid": "e28",
                        "x-amz-apigw-id": "CTqLRGCbPHcFiAg=",
                        "x-amzn-trace-id": "Root=1-350;Sampled=0",
                    },
                    "RetryAttempts": 0,
                },
                "NextToken": "1111111111",
                "Schemas": [
                    {
                        "LastModified": "LastModified",
                        "SchemaName": "aws.autoscaling.AWSAPICallViaCloudTrail",
                        "VersionCount": 1,
                    }
                ],
            }
        ]

        list_schemas_response = schemas_api_caller.list_schemas(registry_name, "next_token", max_items)
        self.assertEqual(len(list_schemas_response["schemas"]), 1)
        self.assertEqual(list_schemas_response["schemas"], ["aws.autoscaling.AWSAPICallViaCloudTrail"])
        self.assertEqual(list_schemas_response["next_token"], "1111111111")

        self.client.get_paginator.assert_called_once()
        self.client.get_paginator.assert_called_once_with("list_schemas")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            RegistryName=registry_name,
            PaginationConfig={"StartingToken": "next_token", "MaxItems": max_items, "PageSize": max_items},
        )

    def test_list_schemas_without_next_token(self):
        registry_name = "registry1"
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = [
            {
                "ResponseMetadata": {
                    "RequestId": "123",
                    "HTTPHeaders": {
                        "x-amzn-requestid": "e28",
                        "x-amz-apigw-id": "CTqLRGCbPHcFiAg=",
                        "x-amzn-trace-id": "Root=1-350;Sampled=0",
                    },
                    "RetryAttempts": 0,
                },
                "Schemas": [
                    {
                        "LastModified": "LastModified",
                        "SchemaName": "aws.autoscaling.AWSAPICallViaCloudTrail",
                        "VersionCount": 1,
                    }
                ],
            }
        ]

        list_schemas_response = schemas_api_caller.list_schemas(registry_name, None, max_items)
        self.assertEqual(len(list_schemas_response["schemas"]), 1)
        self.assertEqual(list_schemas_response["schemas"], ["aws.autoscaling.AWSAPICallViaCloudTrail"])
        self.assertEqual(list_schemas_response["next_token"], None)

        self.client.get_paginator.assert_called_once()
        self.client.get_paginator.assert_called_once_with("list_schemas")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            RegistryName=registry_name,
            PaginationConfig={"StartingToken": None, "MaxItems": max_items, "PageSize": max_items},
        )

    def test_list_schemas_raises_not_available_in_region_exception(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = False
        self.client.get_paginator.return_value.paginate.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.list_schemas("registry-name", "next_token", max_items)
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_get_schema_metadata_1p(self):
        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"components":{"schemas":{"AWSEvent":{"properties":{"account":{"type":"string"},"detail":{"$ref":"#/components/schemas/ParameterStoreChange"},'
            '"detail-type":{"type":"string"},"id":{"type":"string"},"region":{"type":"string"},"resources":{"items":{"type":"string"},"type":"array"},'
            '"source":{"type":"string"},"time":{"format":"date-time","type":"string"},"version":{"type":"string"}},"required":["detail-type","resources",'
            '"detail","id","source","time","region","version","account"],"type":"object","x-amazon-events-detail-type":"Parameter Store Change",'
            '"x-amazon-events-source":"aws.ssm"},"ParameterStoreChange":{"properties":{"description":{"type":"string"},"fromVersion":{"type":"string"},'
            '"label":{"type":"string"},"name":{"type":"string"},"operation":{"type":"string"},"toVersion":{"type":"string"},"type":{"type":"string"}},'
            '"required":["name","type","operation"],"type":"object"}}},"info":{"title":"ParameterStoreChange","version":"1.0.0",'
            '"x-amazon-schemas-generated-code-hierarchy":"schema/aws/ssm/parameterstorechange"},"openapi":"3.0.0","paths":{}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }
        registry_name = "registry1"
        schema_name = "aws.ssm@ParameterStoreChange"
        schemas_api_caller = SchemasApiCaller(self.client)
        get_schema_metadata_response = schemas_api_caller.get_schema_metadata(registry_name, schema_name)
        self.assertEqual(get_schema_metadata_response["event_source"], "aws.ssm")
        self.assertEqual(get_schema_metadata_response["event_source_detail_type"], "Parameter Store Change")
        self.assertEqual(get_schema_metadata_response["schema_root_name"], "ParameterStoreChange")
        self.assertEqual(
            "schema.aws.ssm.parameterstorechange", get_schema_metadata_response["schemas_package_hierarchy"]
        )
        self.client.describe_schema.assert_called_once_with(RegistryName=registry_name, SchemaName=schema_name)

    def test_get_schema_metadata_3p_schema(self):
        self.client.describe_schema.return_value = {
            "SchemaArn": "arn:aws:schemas:us-east-1:434418839121:schema/discovered-schemas/order@NewOrder",
            "Tags": {},
            "LastModified": "2019-11-22T01:38:02Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"NewOrder"},"paths":{},"components":{"schemas":{"AWSEvent":{"type":"object",'
            '"required":["detail-type","resources","detail","id","source","time","region","version","account"],"x-amazon-events-detail-type":"NewOrder",'
            '"x-amazon-events-source":"order","properties":{"detail":{"$ref":"#/components/schemas/NewOrder"},"account":{"type":"string"},"detail-type":{'
            '"type":"string"},"id":{"type":"string"},"region":{"type":"string"},"resources":{"type":"array","items":{"type":"object"}},'
            '"source":{"type":"string"},"time":{"type":"string","format":"date-time"},"version":{"type":"string"}}},"NewOrder":{"type":"object",'
            '"required":["productId","orderId","customer"],"properties":{"customer":{"$ref":"#/components/schemas/Customer"},"orderId":{"type":"string"},'
            '"productId":{"type":"string"}}},"Customer":{"type":"object","required":["zip","country","firstName","lastName","city","street"],'
            '"properties":{"city":{"type":"string"},"country":{"type":"string"},"firstName":{"type":"string"},"lastName":{"type":"string"},'
            '"street":{"type":"string"},"zip":{"type":"string"}}}}}}',
            "VersionCreatedDate": "2019-11-22T01:49:50Z",
            "SchemaName": "order@NewOrder",
            "Type": "OpenApi3",
            "SchemaVersion": "9",
        }
        registry_name = "registry1"
        schema_name = "order@NewOrder"
        schemas_api_caller = SchemasApiCaller(self.client)
        get_schema_metadata_response = schemas_api_caller.get_schema_metadata(registry_name, schema_name)
        self.assertEqual("order", get_schema_metadata_response["event_source"])
        self.assertEqual("NewOrder", get_schema_metadata_response["event_source_detail_type"])
        self.assertEqual("NewOrder", get_schema_metadata_response["schema_root_name"])
        self.assertEqual("schema.order.neworder", get_schema_metadata_response["schemas_package_hierarchy"])
        self.client.describe_schema.assert_called_once_with(RegistryName=registry_name, SchemaName=schema_name)

    def test_get_schema_metadata_2p_schema_with_one_type(self):
        self.client.describe_schema.return_value = {
            "openapi": "3.0.0",
            "info": {"version": "1.0.0", "title": "SomeAwesomeSchema"},
            "paths": {},
            "Content": '{"components":{"schemas":{"Some Awesome Schema":{"type":"object","required":["foo","bar","baz"],"properties":{"foo":{"type":"string"},'
            '"bar":{"type":"string"},"baz":{"type":"string"}}}}}}',
            "SchemaName": "2PSchema1",
        }
        registry_name = "registry1"
        schema_name = "2PSchema1"
        schemas_api_caller = SchemasApiCaller(self.client)
        get_schema_metadata_response = schemas_api_caller.get_schema_metadata(registry_name, schema_name)
        self.assertEqual(get_schema_metadata_response["event_source"], DEFAULT_EVENT_SOURCE)
        self.assertEqual(get_schema_metadata_response["event_source_detail_type"], DEFAULT_EVENT_DETAIL_TYPE)
        self.assertEqual(get_schema_metadata_response["schema_root_name"], "Some_Awesome_Schema")
        self.assertEqual(get_schema_metadata_response["schemas_package_hierarchy"], "schema.2pschema1")
        self.client.describe_schema.assert_called_once_with(RegistryName=registry_name, SchemaName=schema_name)

    def test_get_schema_metadata_2p_schema_with_multiple_type(self):
        self.client.describe_schema.return_value = {
            "openapi": "3.0.0",
            "info": {"version": "1.0.0", "title": "SomeAwesomeSchema"},
            "paths": {},
            "Content": r'{"components":{"schemas":{"Some\/Awesome\/Schema.Object.1":{"type":"object","required":["foo","bar","baz"],"properties":{"foo":{"type":"string"},'
            r'"bar":{"type":"string"},"baz":{"type":"string"}}},"Some\/Awesome\/Schema.Object$2":{"type":"object","required":["foo","bar","baz"],'
            '"properties":{"foo":{"type":"string"},"bar":{"type":"string"},"baz":{"type":"string"}}}}}}',
        }
        registry_name = "registry1"
        schema_name = "schema1"
        schemas_api_caller = SchemasApiCaller(self.client)
        get_schema_metadata_response = schemas_api_caller.get_schema_metadata(registry_name, schema_name)
        self.assertEqual(get_schema_metadata_response["event_source"], DEFAULT_EVENT_SOURCE)
        self.assertEqual(get_schema_metadata_response["event_source_detail_type"], DEFAULT_EVENT_DETAIL_TYPE)
        self.assertEqual(get_schema_metadata_response["schema_root_name"], "Some_Awesome_Schema_Object_1")
        self.assertEqual(get_schema_metadata_response["schemas_package_hierarchy"], "schema.schema1")
        self.client.describe_schema.assert_called_once_with(RegistryName=registry_name, SchemaName=schema_name)

    def test_get_schema_metadata_content_not_serializable_raises_exception(self):
        self.client.describe_schema.return_value = {
            "ResponseMetadata": {
                "RequestId": "389418ee-4e15-480a-8459-6c7640de7a26",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "date": "Tue, 29 Oct 2019 07:20:32 GMT",
                    "content-type": "application/json",
                    "content-length": "3767",
                    "connection": "keep-alive",
                    "x-amzn-requestid": "389418ee-4e15-480a-8459-6c7640de7a26",
                    "x-amz-apigw-id": "CUE6AG_wvHcFyWA=",
                    "x-amzn-trace-id": "Root=1-5db7e83f-2c8e2cd03edc82ec7af0946c;Sampled=0",
                },
                "RetryAttempts": 0,
            },
            "Content": '{\n  openapi" : "3.0.0",\n  "info" : {\n    "version" : "1.0.0",\n    "title" : '
            '"CodeCommitPullRequestStateChange"\n  },\n  "paths" : { },\n  "components" : {\n    "schemas" '
            ': {\n      "AWSEvent" : {\n        "type" : "object",\n        "required" : [ "detail-type", '
            '"resources", "id", "source", "time", "detail", "region", "version", "account" ],'
            '\n        "x-amazon-events-detail-type" : "CodeCommit Pull Request State Change",'
            '\n        "x-amazon-events-source" : "aws.codecommit",\n        "properties" : {\n          '
            '"detail" : {\n            "$ref" : "#/components/schemas/CodeCommitPullRequestStateChange"\n  '
            '        },\n          "detail-type" : {\n            "type" : "string"\n          },'
            '\n          "resources" : {\n            "type" : "array",\n            "items" : {\n         '
            '     "type" : "string"\n            }\n          },\n          "id" : {\n            "type" : '
            '"string"\n          },\n          "source" : {\n            "type" : "string"\n          },'
            '\n          "time" : {\n            "type" : "string",\n            "format" : "date-time"\n  '
            '        },\n          "region" : {\n            "type" : "string",\n            "enum" : [ '
            '"ap-south-1", "eu-west-3", "eu-north-1", "eu-west-2", "eu-west-1", "ap-northeast-2", '
            '"ap-northeast-1", "me-south-1", "sa-east-1", "ca-central-1", "ap-east-1", "cn-north-1", '
            '"us-gov-west-1", "ap-southeast-1", "ap-southeast-2", "eu-central-1", "us-east-1", '
            '"us-west-1", "cn-northwest-1", "us-west-2" ]\n          },\n          "version" : {\n         '
            '   "type" : "string"\n          },\n          "account" : {\n            "type" : "string"\n  '
            '        }\n        }\n      },\n      "CodeCommitPullRequestStateChange" : {\n        "type" '
            ': "object",\n        "required" : [ "sourceReference", "lastModifiedDate", "author", '
            '"pullRequestStatus", "isMerged", "notificationBody", "destinationReference", "pullRequestId", '
            '"callerUserArn", "title", "creationDate", "repositoryNames", "destinationCommit", "event", '
            '"sourceCommit" ],\n        "properties" : {\n          "sourceReference" : {\n            '
            '"type" : "string"\n          },\n          "lastModifiedDate" : {\n            "type" : '
            '"string"\n          },\n          "author" : {\n            "type" : "string"\n          },'
            '\n          "pullRequestStatus" : {\n            "type" : "string"\n          },\n          '
            '"isMerged" : {\n            "type" : "string"\n          },\n          "notificationBody" : {'
            '\n            "type" : "string"\n          },\n          "destinationReference" : {\n         '
            '   "type" : "string"\n          },\n          "pullRequestId" : {\n            "type" : '
            '"string"\n          },\n          "callerUserArn" : {\n            "type" : "string"\n        '
            '  },\n          "title" : {\n            "type" : "string"\n          },\n          '
            '"creationDate" : {\n            "type" : "string"\n          },\n          "repositoryNames" '
            ': {\n            "type" : "array",\n            "items" : {\n              "type" : '
            '"string"\n            }\n          },\n          "destinationCommit" : {\n            "type" '
            ': "string"\n          },\n          "event" : {\n            "type" : "string"\n          },'
            '\n          "sourceCommit" : {\n            "type" : "string"\n          }\n        }\n      '
            "}\n    }\n  }\n}\n",
            "LastModified": "LastModified",
            "SchemaArn": "",
            "SchemaName": "aws.codecommit.CodeCommitPullRequestStateChange",
            "SchemaVersion": "1",
            "Type": "OpenApi3",
            "VersionCreatedDate": "VersionCreatedDate",
        }
        registry_name = "registry1"
        schema_name = "schema1"
        schemas_api_caller = SchemasApiCaller(self.client)

        with self.assertRaises(SchemasApiException):
            schemas_api_caller.get_schema_metadata(registry_name, schema_name)

    def test_get_schema_metadata_raises_not_available_in_region_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.describe_schema.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.get_schema_metadata("registry-name", "schema-name")
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_get_latest_schema_version(self):
        registry_name = "registry1"
        schema_name = "schema1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = [
            {
                "ResponseMetadata": {},
                "SchemaVersions": [
                    {"SchemaName": "schema1", "SchemaVersion": "1"},
                    {"SchemaName": "schema1", "SchemaVersion": "2"},
                    {"SchemaName": "schema1", "SchemaVersion": "3"},
                ],
            }
        ]

        get_latest_schema_version_response = schemas_api_caller.get_latest_schema_version(registry_name, schema_name)
        self.assertEqual(get_latest_schema_version_response, "3")
        self.client.get_paginator.assert_called_once()
        self.client.get_paginator.assert_called_once_with("list_schema_versions")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            RegistryName=registry_name, SchemaName=schema_name, PaginationConfig={"StartingToken": None}
        )

    def test_get_latest_schema_version_raises_not_available_in_region_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = False
        self.client.get_paginator.return_value.paginate.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.get_latest_schema_version("registry-name", "schema-name")
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_list_registries_throws_exception_when_result_set_is_empty(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = []
        with self.assertRaises(ResourceNotFound) as ctx:
            schemas_api_caller.list_registries(None, max_items)
        msg = "No Registries found. This should not be possible, please raise an issue."
        self.assertEqual(str(ctx.exception), msg)

    def test_list_schemas_throws_exception_when_result_set_is_empty(self):
        max_items = 10
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.can_paginate.return_value = True
        self.client.get_paginator.return_value.paginate.return_value = []
        with self.assertRaises(ResourceNotFound) as ctx:
            schemas_api_caller.list_schemas("aws.events", None, max_items)
        msg = "No Schemas found for registry %s" % "aws.events"
        self.assertEqual(str(ctx.exception), msg)

    def test_download_source_code_binding(self):
        response = io.BytesIO(b"some initial binary data: \x00\x01")
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_code_binding_source.return_value = {"Body": response}
        with tempfile.TemporaryFile() as download_dir:
            schemas_api_caller.download_source_code_binding(
                "Java8", "aws.events", "aws.batch.BatchJobStateChange", "1", download_dir
            )

    def test_download_source_code_binding_raises_not_available_in_region_exception(self):
        response = io.BytesIO(b"some initial binary data: \x00\x01")
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_code_binding_source.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.download_source_code_binding(
                "Java8", "aws.events", "aws.batch.BatchJobStateChange", "1", "download_dir"
            )
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_put_code_binding_with_conflict_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.put_code_binding.side_effect = [
            botocore.exceptions.ClientError(
                {"Error": {"Code": "ConflictException", "Message": "ConflictException"}}, "operation"
            )
        ]
        schemas_api_caller.put_code_binding("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")
        self.client.put_code_binding.assert_called_once_with(
            Language="Java8", RegistryName="aws.events", SchemaName="aws.batch.BatchJobStateChange", SchemaVersion="1"
        )

    def test_put_code_binding_with_not_found_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.put_code_binding.side_effect = [
            botocore.exceptions.ClientError(
                {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
            )
        ]
        with self.assertRaises(Exception):
            schemas_api_caller.put_code_binding("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")

    def test_put_code_binding_raises_not_available_in_region_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.put_code_binding.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.put_code_binding("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_poll_for_code_generation_completion(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_waiter.return_value.wait.return_value = None
        schemas_api_caller.poll_for_code_binding_status("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")

    def test_poll_for_code_generation_completion_with_failed_status(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_waiter.return_value.wait.return_value = None
        schemas_api_caller.poll_for_code_binding_status("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_waiter.return_value.wait.side_effect = WaiterError(
            name="failed", reason="Waiter encountered a terminal failure state", last_response="failed"
        )
        with self.assertRaises(WaiterError):
            schemas_api_caller.poll_for_code_binding_status("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")

    def test_poll_for_code_generation_completion_raises_not_available_in_region_exception(self):
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_waiter.return_value.wait.return_value = None
        schemas_api_caller.poll_for_code_binding_status("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_waiter.return_value.wait.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        with self.assertRaises(NotAvailableInRegion) as ctx:
            schemas_api_caller.poll_for_code_binding_status("Java8", "aws.events", "aws.batch.BatchJobStateChange", "1")
        msg = (
            "EventBridge Schemas are not available in provided region. Please check "
            "AWS doc for Schemas supported regions."
        )
        self.assertEqual(str(ctx.exception), msg)

    def test_discover_schema(self):
        event_contents = '{"key1": "value1"}'
        schema_type = "OpenApi3"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.get_discovered_schema.return_value = {"Content": "Discovered Schema"}

        discover_schema_response = schemas_api_caller.discover_schema(event_contents, schema_type)
        self.assertEqual(discover_schema_response, "Discovered Schema")
        self.client.get_discovered_schema.assert_called_once_with(Events=[event_contents], Type=schema_type)

    def test_create_schema(self):
        schema_contents = '{"key1": "value1"}'
        schema_type = "OpenApi3"
        registry_name = "registry1"
        schema_name = "schema1"
        schemas_api_caller = SchemasApiCaller(self.client)

        create_schema_response = schemas_api_caller.create_schema(
            schema_contents, registry_name, schema_name, schema_type
        )
        self.assertTrue(create_schema_response)
        self.client.create_schema.assert_called_once_with(
            Content=schema_contents, RegistryName=registry_name, SchemaName=schema_name, Type=schema_type
        )

    def test_update_schema(self):
        schema_contents = '{"key1": "value1"}'
        schema_type = "OpenApi3"
        registry_name = "registry1"
        schema_name = "schema1"
        schemas_api_caller = SchemasApiCaller(self.client)

        update_schema_response = schemas_api_caller.update_schema(
            schema_contents, registry_name, schema_name, schema_type
        )
        self.assertTrue(update_schema_response)
        self.client.update_schema.assert_called_once_with(
            Content=schema_contents, RegistryName=registry_name, SchemaName=schema_name, Type=schema_type
        )

    def test_get_schema(self):
        schema_name = "schema1"
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.describe_schema.return_value = {"Content": "Schema contents"}

        get_schema_response = schemas_api_caller.get_schema(registry_name, schema_name)
        self.assertEqual(get_schema_response, "Schema contents")
        self.client.describe_schema.assert_called_once_with(
            RegistryName=registry_name,
            SchemaName=schema_name,
        )

    def test_check_registry_exists(self):
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.describe_registry.return_value = "Registry"

        get_registry_exists = schemas_api_caller.check_registry_exists(registry_name)
        self.assertTrue(get_registry_exists)
        self.client.describe_registry.assert_called_once_with(
            RegistryName=registry_name,
        )

    def test_check_registry_not_exists(self):
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.describe_registry.side_effect = self.not_found_exception()

        get_registry_exists = schemas_api_caller.check_registry_exists(registry_name)
        self.assertFalse(get_registry_exists)
        self.client.describe_registry.assert_called_once_with(
            RegistryName=registry_name,
        )

    def test_create_registry(self):
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)

        create_registry_response = schemas_api_caller.create_registry(registry_name)
        self.assertTrue(create_registry_response)
        self.client.create_registry.assert_called_once_with(
            RegistryName=registry_name,
        )

    def test_create_registry_if_already_exists(self):
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.create_registry.side_effect = ClientError({"Error": {"Code": "ConflictException"}}, "create")

        create_registry_response = schemas_api_caller.create_registry(registry_name)
        self.assertFalse(create_registry_response)
        self.client.create_registry.assert_called_once_with(
            RegistryName=registry_name,
        )

    def test_delete_schema(self):
        schema_name = "schema1"
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)

        get_schema_response = schemas_api_caller.delete_schema(registry_name, schema_name)
        self.assertTrue(get_schema_response)
        self.client.delete_schema.assert_called_once_with(
            RegistryName=registry_name,
            SchemaName=schema_name,
        )

    def test_delete_schema_doesnt_exist(self):
        schema_name = "schema1"
        registry_name = "registry1"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.delete_schema.side_effect = self.not_found_exception()

        deleted = schemas_api_caller.delete_schema(registry_name, schema_name)
        self.assertFalse(deleted)

    def test_delete_version(self):
        schema_name = "schema1"
        registry_name = "registry1"
        version_number = "33"
        schemas_api_caller = SchemasApiCaller(self.client)

        delete_version_response = schemas_api_caller.delete_version(registry_name, schema_name, version_number)
        self.assertTrue(delete_version_response)
        self.client.delete_schema_version.assert_called_once_with(
            RegistryName=registry_name,
            SchemaName=schema_name,
            SchemaVersion=version_number,
        )

    def test_delete_version_with_error(self):
        schema_name = "schema1"
        registry_name = "registry1"
        version_number = "33"
        schemas_api_caller = SchemasApiCaller(self.client)
        boto_error = ClientError({}, "delete")  # generic exception
        self.client.delete_schema_version.side_effect = boto_error

        with self.assertRaises(Exception) as ctx:
            schemas_api_caller.delete_version(registry_name, schema_name, version_number)
        self.assertEqual(ctx.exception, boto_error)

    def test_delete_version_doesnt_exist(self):
        schema_name = "schema1"
        registry_name = "registry1"
        version_number = "33"
        schemas_api_caller = SchemasApiCaller(self.client)
        self.client.delete_schema_version.side_effect = self.not_found_exception()

        deleted = schemas_api_caller.delete_version(registry_name, schema_name, version_number)
        self.assertFalse(deleted)

    def not_found_exception(self):
        return ClientError({"Error": {"Code": "NotFoundException"}}, "operation")
