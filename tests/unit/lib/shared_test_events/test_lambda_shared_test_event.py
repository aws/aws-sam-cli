from unittest.mock import Mock, patch
from unittest import TestCase
from parameterized import parameterized

import botocore

from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound, NotAvailableInRegion
from samcli.commands.remote.exceptions import DuplicateEventName, InvalidSchema, EventTooLarge
from samcli.lib.schemas.schemas_api_caller import SchemasApiCaller
from samcli.lib.shared_test_events.lambda_shared_test_event import (
    LambdaSharedTestEvent,
    NoPermissionExceptionWrapper,
    MAX_EVENT_SIZE,
)
from samcli.lib.utils.cloudformation import CloudFormationResourceSummary
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION


class TestSchemasCommand(TestCase):
    def setUp(self):
        self.client = Mock()
        self.schemas_api_caller = SchemasApiCaller(self.client)
        self.lambda_client = Mock()
        self.lambda_client.get_function_configuration.return_value = {"FunctionName": "myFunction"}

    def _cfn_resource(self, name, physical_id=None):
        return CloudFormationResourceSummary(AWS_LAMBDA_FUNCTION, name, physical_id if physical_id else name)

    def test_validate_schema_dict(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        schema = {"components": {"schemas": "SCHEMAS"}}
        lambda_test_event._validate_schema_dict(schema)

    def test_validate_invalid_schema_dict(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        schema = {"schemas": "SCHEMAS"}
        try:
            lambda_test_event._validate_schema_dict(schema)
            self.fail("It should have raised an exception")
        except InvalidSchema as e:
            self.assertEqual(e.message, 'Schema {"schemas": "SCHEMAS"} is not valid')

    def test_validate_event_size(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        # It only validates size
        reasonable_event = "small_event"
        lambda_test_event._validate_event_size(reasonable_event)

        big_event = "x" * (MAX_EVENT_SIZE + 1)
        try:
            lambda_test_event._validate_event_size(big_event)
            self.fail("It should have raised an exception")
        except EventTooLarge as e:
            self.assertIn("Event is bigger than the accepted", e.message)

    @parameterized.expand(
        [
            ("myFunction", "_myFunction-schema"),
            ("arn:aws:lambda:us-east-1:123456789123:function:myFunction", "_myFunction-schema"),
        ]
    )
    def test_get_schema_name(self, function_name, expected_schema):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        function_resource = self._cfn_resource(function_name)
        self.assertEqual(lambda_test_event._get_schema_name(function_resource), expected_schema)

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1"])
    def test_delete_event_multiple_events_success(self, _list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.return_value = {"registryName": "someRegistry"}
        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}},"test2":{"value":{"key":"number2"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        lambda_test_event.delete_event("test2", self._cfn_resource("MyFunction"))

        self.client.update_schema.assert_called_once_with(
            Content='{"openapi": "3.0.0", "info": {"version": "1.0.0", "title": "Event"}, "paths": {}, "components": {"schemas": {"Event": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string"}}}}, "examples": {"test1": {"value": {"key": "number1"}}}}}',
            RegistryName="lambda-testevent-schemas",
            SchemaName="_MyFunction-schema",
            Type="OpenApi3",
        )

    def test_delete_event_one_event_success(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.return_value = {"registryName": "someRegistry"}
        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        self.client.list_schema_versions.return_value = {
            "NextToken": "string",
            "SchemaVersions": [
                {"SchemaArn": "string", "SchemaName": "string", "SchemaVersion": "string", "Type": "OpenApi3"},
            ],
        }

        lambda_test_event.delete_event("test1", self._cfn_resource("MyFunction"))

        self.client.delete_schema.assert_called_once_with(
            RegistryName="lambda-testevent-schemas", SchemaName="_MyFunction-schema"
        )

    def test_delete_no_registry(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.delete_event("myEvent", self._cfn_resource("MyFunction"))

            msg = "lambda-testevent-schemas registry not found. There are no saved events."
            self.assertEqual(str(ctx.exception), msg)

    def test_delete_no_schema(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.return_value = {"registry": "someRegistry"}
        self.client.describe_schema.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.delete_event("myEvent", self._cfn_resource("MyFunction", "PhysicalId"))

            msg = "No events found for function myFunction"
            self.assertEqual(str(ctx.exception), msg)

    def test_delete_no_event(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.delete_event("myEvent", self._cfn_resource("MyFunction"))

            msg = "Event myEvent not found"
            self.assertEqual(str(ctx.exception), msg)

    def test_delete_not_available_error(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )

        with self.assertRaises(NotAvailableInRegion) as ctx:
            lambda_test_event.delete_event("myEvent", self._cfn_resource("MyFunction"))

            msg = (
                "EventBridge Schemas are not available in provided region. Please check "
                "AWS doc for Schemas supported regions."
            )
            self.assertEqual(str(ctx.exception), msg)

    def test_create_event_new_schema_success(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        self.client.get_discovered_schema.return_value = {
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}}}}'
        }

        lambda_test_event.create_event("test1", self._cfn_resource("MyFunction"), '{"key": "number1"}')

        self.client.get_discovered_schema.assert_called_once_with(Events=['{"key": "number1"}'], Type="OpenApi3")

        self.client.create_schema.assert_called_once_with(
            Content='{"openapi": "3.0.0", "info": {"version": "1.0.0", "title": "Event"}, "paths": {}, "components": {"schemas": {"Event": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string"}}}}, "examples": {"test1": {"value": {"key": "number1"}}}}}',
            RegistryName="lambda-testevent-schemas",
            SchemaName="_MyFunction-schema",
            Type="OpenApi3",
        )

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1"])
    def test_create_event_schema_exists_success(self, _list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        lambda_test_event.create_event("test2", self._cfn_resource("MyFunction"), '{"key": "number2"}')

        self.client.update_schema.assert_called_once_with(
            Content='{"openapi": "3.0.0", "info": {"version": "1.0.0", "title": "Event"}, "paths": {}, "components": {"schemas": {"Event": {"type": "object", "required": ["key"], "properties": {"key": {"type": "string"}}}}, "examples": {"test1": {"value": {"key": "number1"}}, "test2": {"value": {"key": "number2"}}}}}',
            RegistryName="lambda-testevent-schemas",
            SchemaName="_MyFunction-schema",
            Type="OpenApi3",
        )

    def test_create_event_no_registry(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        self.client.describe_schema.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        self.client.get_discovered_schema.return_value = {
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}}}}'
        }

        lambda_test_event.create_event("test1", self._cfn_resource("MyFunction"), '{"key": "number1"}')

        self.client.create_registry.assert_called_once_with(RegistryName="lambda-testevent-schemas")

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1"])
    def test_create_event_duplicate_event(self, list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        with self.assertRaises(DuplicateEventName) as ctx:
            lambda_test_event.create_event("test1", self._cfn_resource("MyFunction"), '{"key": "number2"}')

            self.client.get_paginator.assert_called_once_with("list_schema_versions")

            msg = "Event test1 already exists"
            self.assertEqual(str(ctx.exception), msg)

    def test_create_not_available_error(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )

        with self.assertRaises(NotAvailableInRegion) as ctx:
            lambda_test_event.create_event("test1", self._cfn_resource("MyFunction"), '{"key": "number2"}')

            msg = (
                "EventBridge Schemas are not available in provided region. Please check "
                "AWS doc for Schemas supported regions."
            )
            self.assertEqual(str(ctx.exception), msg)

    def test_get_event_success(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        event = lambda_test_event.get_event("test1", self._cfn_resource("MyFunction"))

        self.assertEqual(event, '{"key": "number1"}')

    def test_get_event_no_registry(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.get_event("myEvent", self._cfn_resource("MyFunction"))

            msg = "lambda-testevent-schemas registry not found. There are no saved events."
            self.assertEqual(str(ctx.exception), msg)

    def test_get_event_no_schema(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.get_event("myEvent", self._cfn_resource("MyFunction", "PhysicalId"))

            msg = "No events found for function myFunction"
            self.assertEqual(str(ctx.exception), msg)

    def test_get_event_no_event(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)
        self.client.describe_registry.return_value = {"registry": "someRegistry"}

        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.get_event("myEvent", self._cfn_resource("MyFunction"))

            msg = "Event myEvent not found"
            self.assertEqual(str(ctx.exception), msg)

    def test_get_not_available_error(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )

        with self.assertRaises(NotAvailableInRegion) as ctx:
            lambda_test_event.get_event("eventName", self._cfn_resource("MyFunction"))

            msg = (
                "EventBridge Schemas are not available in provided region. Please check "
                "AWS doc for Schemas supported regions."
            )
            self.assertEqual(str(ctx.exception), msg)

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1"])
    def test_limit_version_under_cap(self, list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        lambda_test_event.limit_versions("_MyFunction-schema", "myRegistry")

        list_schema_versions_mock.assert_called_once_with("myRegistry", "_MyFunction-schema")

        self.client.delete_schema_version.assert_not_called()

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1", "2", "3", "4", "5", "6"])
    def test_limit_version_over_cap(self, list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        lambda_test_event.limit_versions("_MyFunction-schema", "myRegistry")

        self.client.delete_schema_version.assert_called_once_with(
            RegistryName="myRegistry",
            SchemaName="_MyFunction-schema",
            SchemaVersion="1",
        )

    @patch.object(SchemasApiCaller, "list_schema_versions", return_value=["1"])
    def test_list_events(self, _list_schema_versions_mock):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.return_value = {"registryName": "someRegistry"}
        self.client.describe_schema.return_value = {
            "SchemaArn": "",
            "Tags": {},
            "LastModified": "2019-11-25T20:33:14Z",
            "Content": '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"Event"},"paths":{},"components":{"schemas":{"Event":{"type":"object","required":["key"],"properties":{"key":{"type":"string"}}}},"examples":{"test1":{"value":{"key":"number1"}},"test2":{"value":{"key":"number2"}}}}}',
            "VersionCreatedDate": "2019-11-25T20:33:14Z",
            "SchemaName": "aws.ssm@ParameterStoreChange",
            "Type": "OpenApi3",
            "SchemaVersion": "1",
        }

        output = lambda_test_event.list_events(self._cfn_resource("MyFunction"))

        expected = "test1\ntest2"

        self.assertEqual(output, expected)

    def test_list_no_schema(self):
        lambda_test_event = LambdaSharedTestEvent(self.schemas_api_caller, self.lambda_client)

        self.client.describe_registry.return_value = {"registry": "someRegistry"}
        self.client.describe_schema.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "NotFoundException", "Message": "NotFoundException"}}, "operation"
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            lambda_test_event.list_events(self._cfn_resource("MyFunction"))

            msg = "No events found for function myFunction"
            self.assertEqual(str(ctx.exception), msg)


class TestNoPermissionWrapper(TestCase):
    def test_return_value(self):
        api = Mock()
        wrapped = NoPermissionExceptionWrapper(api)
        api.method1.return_value = "object"
        value = wrapped.method1()
        api.method1.assert_called_with()
        self.assertEqual(value, "object")

    def test_arguments(self):
        api = Mock()
        wrapped = NoPermissionExceptionWrapper(api)
        api.method2.return_value = "object2"
        value = wrapped.method2(1, 2, 3, a="10", b="20")
        api.method2.assert_called_with(1, 2, 3, a="10", b="20")
        self.assertEqual(value, "object2")

    def test_exception(self):
        api = Mock()
        wrapped = NoPermissionExceptionWrapper(api)
        api.method_with_error.side_effect = Exception("Exception 1")
        try:
            wrapped.method_with_error()
            self.Fail("It should have thrown an Exception")
        except Exception as e:
            self.assertEqual(e.args[0], "Exception 1")

    def test_permissions_exception(self):
        api = Mock()
        wrapped = NoPermissionExceptionWrapper(api)
        permissions_exception = botocore.exceptions.ClientError({"Error": {"Code": "ForbiddenException"}}, "operation")
        api.method_with_permission_error.side_effect = permissions_exception
        try:
            wrapped.method_with_permission_error()
            self.Fail("It should have thrown an Exception")
        except Exception as e:
            self.assertIn("Update your role to have the necessary permissions", e.message)
