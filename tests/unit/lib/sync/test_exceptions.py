from unittest import TestCase
from unittest.mock import MagicMock
from samcli.lib.sync.exceptions import (
    MissingPhysicalResourceError,
    NoLayerVersionsFoundError,
    SyncFlowException,
    MissingFunctionBuildDefinition,
    InvalidRuntimeDefinitionForFunction,
)


class TestSyncFlowException(TestCase):
    def test_exception(self):
        sync_flow_mock = MagicMock()
        exception_mock = MagicMock()
        exception = SyncFlowException(sync_flow_mock, exception_mock)
        self.assertEqual(exception.sync_flow, sync_flow_mock)
        self.assertEqual(exception.exception, exception_mock)


class TestMissingPhysicalResourceError(TestCase):
    def test_exception(self):
        exception = MissingPhysicalResourceError("A")
        self.assertEqual(exception.resource_identifier, "A")

    def test_exception_with_mapping(self):
        physical_mapping = MagicMock()
        exception = MissingPhysicalResourceError("A", physical_mapping)
        self.assertEqual(exception.resource_identifier, "A")
        self.assertEqual(exception.physical_resource_mapping, physical_mapping)


class TestNoLayerVersionsFoundError(TestCase):
    def test_exception(self):
        exception = NoLayerVersionsFoundError("layer_name_arn")
        self.assertEqual(exception.layer_name_arn, "layer_name_arn")


class TestMissingFunctionBuildDefinition(TestCase):
    def test_exception(self):
        function_logical_id = "function_logical_id"
        exception = MissingFunctionBuildDefinition(function_logical_id)
        self.assertEqual(exception.function_logical_id, function_logical_id)


class TestInvalidRuntimeDefinitionForFunction(TestCase):
    def test_exception(self):
        function_logical_id = "function_logical_id"
        exception = InvalidRuntimeDefinitionForFunction(function_logical_id)
        self.assertEqual(exception.function_logical_id, function_logical_id)
