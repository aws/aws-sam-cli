"""
Unit tests for the pipeline module.

Tests for TemplateProcessor protocol and ProcessingPipeline class.
Validates requirements 1.1, 1.2, 1.3, 1.4.
"""

import pytest
from typing import List, Optional

from samcli.lib.cfn_language_extensions import (
    TemplateProcessor,
    ProcessingPipeline,
    TemplateProcessingContext,
    InvalidTemplateException,
)


class MockProcessor:
    """A mock processor that records calls and can modify the context."""

    def __init__(self, name: str, modification: Optional[dict] = None, should_raise: Optional[Exception] = None):
        """
        Initialize the mock processor.

        Args:
            name: Identifier for this processor.
            modification: Dict to merge into context.fragment when processed.
            should_raise: Exception to raise when process_template is called.
        """
        self.name = name
        self.modification = modification or {}
        self.should_raise = should_raise
        self.call_count = 0
        self.received_contexts: List[TemplateProcessingContext] = []

    def process_template(self, context: TemplateProcessingContext) -> None:
        """Process the template by recording the call and optionally modifying context."""
        self.call_count += 1
        self.received_contexts.append(context)

        if self.should_raise:
            raise self.should_raise

        # Apply modifications to the fragment
        context.fragment.update(self.modification)


class TestTemplateProcessorProtocol:
    """Tests for TemplateProcessor protocol."""

    def test_mock_processor_implements_protocol(self):
        """MockProcessor should implement TemplateProcessor protocol."""
        processor = MockProcessor("test")
        assert isinstance(processor, TemplateProcessor)

    def test_protocol_requires_process_template_method(self):
        """TemplateProcessor protocol requires process_template method."""

        class ValidProcessor:
            def process_template(self, context: TemplateProcessingContext) -> None:
                pass

        processor = ValidProcessor()
        assert isinstance(processor, TemplateProcessor)

    def test_class_without_method_is_not_processor(self):
        """Class without process_template is not a TemplateProcessor."""

        class InvalidProcessor:
            pass

        processor = InvalidProcessor()
        assert not isinstance(processor, TemplateProcessor)

    def test_class_with_wrong_signature_is_still_protocol_match(self):
        """Protocol only checks method existence, not signature at runtime."""

        # Note: Protocol runtime checking only verifies method existence
        class ProcessorWithDifferentSignature:
            def process_template(self):  # Missing context parameter
                pass

        processor = ProcessorWithDifferentSignature()
        # Runtime protocol check only verifies method exists
        assert isinstance(processor, TemplateProcessor)


class TestProcessingPipeline:
    """Tests for ProcessingPipeline class."""

    def test_empty_pipeline_returns_fragment(self):
        """Empty pipeline should return the original fragment unchanged."""
        pipeline = ProcessingPipeline([])
        context = TemplateProcessingContext(fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}})

        result = pipeline.process_template(context)

        assert result == {"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}

    def test_single_processor_is_executed(self):
        """Single processor should be executed."""
        processor = MockProcessor("single", modification={"Processed": True})
        pipeline = ProcessingPipeline([processor])
        context = TemplateProcessingContext(fragment={"Resources": {}})

        result = pipeline.process_template(context)

        assert processor.call_count == 1
        assert result["Processed"] is True

    def test_processors_executed_in_order(self):
        """Requirement 1.1: Processors should be executed in order."""
        execution_order = []

        class OrderTrackingProcessor:
            def __init__(self, name: str):
                self.name = name

            def process_template(self, context: TemplateProcessingContext) -> None:
                execution_order.append(self.name)

        processors = [
            OrderTrackingProcessor("first"),
            OrderTrackingProcessor("second"),
            OrderTrackingProcessor("third"),
        ]
        pipeline = ProcessingPipeline(processors)
        context = TemplateProcessingContext(fragment={})

        pipeline.process_template(context)

        assert execution_order == ["first", "second", "third"]

    def test_context_passed_through_processors(self):
        """Requirement 1.2: Same context should be passed through each processor."""
        processor1 = MockProcessor("first")
        processor2 = MockProcessor("second")
        processor3 = MockProcessor("third")

        pipeline = ProcessingPipeline([processor1, processor2, processor3])
        context = TemplateProcessingContext(fragment={"Resources": {}})

        pipeline.process_template(context)

        # All processors should receive the same context object
        assert processor1.received_contexts[0] is context
        assert processor2.received_contexts[0] is context
        assert processor3.received_contexts[0] is context

    def test_modifications_accumulate(self):
        """Modifications from each processor should accumulate in context."""
        processor1 = MockProcessor("first", modification={"Step1": "done"})
        processor2 = MockProcessor("second", modification={"Step2": "done"})
        processor3 = MockProcessor("third", modification={"Step3": "done"})

        pipeline = ProcessingPipeline([processor1, processor2, processor3])
        context = TemplateProcessingContext(fragment={"Resources": {}})

        result = pipeline.process_template(context)

        assert result["Step1"] == "done"
        assert result["Step2"] == "done"
        assert result["Step3"] == "done"
        assert result["Resources"] == {}

    def test_returns_processed_fragment(self):
        """Requirement 1.3: Should return the processed template fragment."""
        processor = MockProcessor("modifier", modification={"NewKey": "NewValue"})
        pipeline = ProcessingPipeline([processor])
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        result = pipeline.process_template(context)

        assert result is context.fragment
        assert result["NewKey"] == "NewValue"
        assert result["Resources"]["Bucket"]["Type"] == "AWS::S3::Bucket"

    def test_exception_propagation_stops_pipeline(self):
        """Requirement 1.4: Exception should stop pipeline and propagate."""
        processor1 = MockProcessor("first")
        processor2 = MockProcessor("failing", should_raise=InvalidTemplateException("Test error"))
        processor3 = MockProcessor("third")

        pipeline = ProcessingPipeline([processor1, processor2, processor3])
        context = TemplateProcessingContext(fragment={})

        with pytest.raises(InvalidTemplateException) as exc_info:
            pipeline.process_template(context)

        assert str(exc_info.value) == "Test error"
        assert processor1.call_count == 1
        assert processor2.call_count == 1
        assert processor3.call_count == 0  # Should not be executed

    def test_exception_propagation_preserves_exception_type(self):
        """Requirement 1.4: Original exception type should be preserved."""

        class CustomException(Exception):
            pass

        processor = MockProcessor("failing", should_raise=CustomException("Custom error"))
        pipeline = ProcessingPipeline([processor])
        context = TemplateProcessingContext(fragment={})

        with pytest.raises(CustomException):
            pipeline.process_template(context)

    def test_exception_in_first_processor(self):
        """Exception in first processor should prevent all subsequent processors."""
        processor1 = MockProcessor("failing", should_raise=InvalidTemplateException("First processor failed"))
        processor2 = MockProcessor("second")
        processor3 = MockProcessor("third")

        pipeline = ProcessingPipeline([processor1, processor2, processor3])
        context = TemplateProcessingContext(fragment={})

        with pytest.raises(InvalidTemplateException):
            pipeline.process_template(context)

        assert processor1.call_count == 1
        assert processor2.call_count == 0
        assert processor3.call_count == 0

    def test_exception_in_last_processor(self):
        """Exception in last processor should still propagate."""
        processor1 = MockProcessor("first", modification={"Step1": "done"})
        processor2 = MockProcessor("second", modification={"Step2": "done"})
        processor3 = MockProcessor("failing", should_raise=InvalidTemplateException("Last processor failed"))

        pipeline = ProcessingPipeline([processor1, processor2, processor3])
        context = TemplateProcessingContext(fragment={})

        with pytest.raises(InvalidTemplateException) as exc_info:
            pipeline.process_template(context)

        assert "Last processor failed" in str(exc_info.value)
        assert processor1.call_count == 1
        assert processor2.call_count == 1
        assert processor3.call_count == 1
        # Modifications from successful processors should still be in context
        assert context.fragment["Step1"] == "done"
        assert context.fragment["Step2"] == "done"

    def test_processors_property_returns_copy(self):
        """processors property should return a copy of the processor list."""
        processor1 = MockProcessor("first")
        processor2 = MockProcessor("second")
        pipeline = ProcessingPipeline([processor1, processor2])

        processors = pipeline.processors

        assert len(processors) == 2
        assert processors[0] is processor1
        assert processors[1] is processor2

        # Modifying returned list should not affect pipeline
        processors.append(MockProcessor("third"))
        assert len(pipeline.processors) == 2


class TestProcessingPipelineIntegration:
    """Integration tests for ProcessingPipeline with realistic scenarios."""

    def test_pipeline_with_context_state_modification(self):
        """Processors can modify context state beyond just fragment."""

        class ParsedTemplateProcessor:
            def process_template(self, context: TemplateProcessingContext) -> None:
                from samcli.lib.cfn_language_extensions import ParsedTemplate

                context.parsed_template = ParsedTemplate(resources=context.fragment.get("Resources", {}))

        class ConditionProcessor:
            def process_template(self, context: TemplateProcessingContext) -> None:
                context.resolved_conditions["IsProd"] = True

        pipeline = ProcessingPipeline([ParsedTemplateProcessor(), ConditionProcessor()])
        context = TemplateProcessingContext(fragment={"Resources": {"Bucket": {"Type": "AWS::S3::Bucket"}}})

        pipeline.process_template(context)

        assert context.parsed_template is not None
        assert "Bucket" in context.parsed_template.resources
        assert context.resolved_conditions["IsProd"] is True

    def test_pipeline_with_parameter_values(self):
        """Pipeline should work with parameter values in context."""

        class ParameterResolver:
            def process_template(self, context: TemplateProcessingContext) -> None:
                env = context.parameter_values.get("Environment", "dev")
                context.fragment["ResolvedEnv"] = env

        pipeline = ProcessingPipeline([ParameterResolver()])
        context = TemplateProcessingContext(fragment={"Resources": {}}, parameter_values={"Environment": "production"})

        result = pipeline.process_template(context)

        assert result["ResolvedEnv"] == "production"

    def test_pipeline_preserves_original_fragment_structure(self):
        """Pipeline should preserve nested structure in fragment."""

        class NoOpProcessor:
            def process_template(self, context: TemplateProcessingContext) -> None:
                pass

        pipeline = ProcessingPipeline([NoOpProcessor()])
        original_fragment = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "Test template",
            "Parameters": {"Env": {"Type": "String", "Default": "dev"}},
            "Resources": {
                "Bucket": {
                    "Type": "AWS::S3::Bucket",
                    "Properties": {"BucketName": "my-bucket", "Tags": [{"Key": "Env", "Value": "dev"}]},
                }
            },
            "Outputs": {"BucketArn": {"Value": {"Fn::GetAtt": ["Bucket", "Arn"]}}},
        }
        context = TemplateProcessingContext(fragment=original_fragment)

        result = pipeline.process_template(context)

        assert result == original_fragment


class TestModuleExports:
    """Tests for module exports."""

    def test_template_processor_exported(self):
        """TemplateProcessor should be exported from package."""
        from samcli.lib.cfn_language_extensions import TemplateProcessor

        assert TemplateProcessor is not None

    def test_processing_pipeline_exported(self):
        """ProcessingPipeline should be exported from package."""
        from samcli.lib.cfn_language_extensions import ProcessingPipeline

        assert ProcessingPipeline is not None

    def test_can_create_pipeline_from_package_import(self):
        """Should be able to create pipeline using package imports."""
        from samcli.lib.cfn_language_extensions import (
            ProcessingPipeline,
            TemplateProcessingContext,
        )

        pipeline = ProcessingPipeline([])
        context = TemplateProcessingContext(fragment={"Resources": {}})
        result = pipeline.process_template(context)

        assert result == {"Resources": {}}


# =============================================================================
# Parametrized Tests (replacing property-based tests)
# =============================================================================


class TestPipelineProperties:
    """Parametrized tests for ProcessingPipeline."""

    @pytest.mark.parametrize(
        "processor_names",
        [
            [],
            ["alpha", "beta", "gamma"],
            ["p1", "p2", "p3", "p4", "p5"],
        ],
        ids=["empty", "three-processors", "five-processors"],
    )
    def test_pipeline_execution_order_property(self, processor_names: List[str]):
        """
        # Feature: cfn-language-extensions-python, Property 1: Pipeline Execution Order

        For any list of template processors, the ProcessingPipeline SHALL execute
        them in the exact order they appear in the list.

        **Validates: Requirements 1.1, 1.2**
        """
        execution_order: List[str] = []
        contexts_received: List[TemplateProcessingContext] = []

        class OrderTrackingProcessor:
            def __init__(self, name: str):
                self.name = name

            def process_template(self, context: TemplateProcessingContext) -> None:
                execution_order.append(self.name)
                contexts_received.append(context)

        processors: List[TemplateProcessor] = [OrderTrackingProcessor(name) for name in processor_names]
        pipeline = ProcessingPipeline(processors)
        context = TemplateProcessingContext(fragment={"Resources": {}})

        result = pipeline.process_template(context)

        assert execution_order == processor_names
        for received_context in contexts_received:
            assert received_context is context
        assert result is context.fragment

    @pytest.mark.parametrize(
        "num_processors,failing_index",
        [
            (3, 0),
            (5, 2),
            (4, 3),
        ],
        ids=["fail-first-of-3", "fail-middle-of-5", "fail-last-of-4"],
    )
    def test_pipeline_exception_propagation_property(self, num_processors: int, failing_index: int):
        """
        # Feature: cfn-language-extensions-python, Property 2: Pipeline Exception Propagation

        For any pipeline where a processor raises InvalidTemplateException,
        subsequent processors SHALL NOT be executed and the exception SHALL
        propagate to the caller.

        **Validates: Requirements 1.4**
        """
        executed_processors: List[int] = []

        class TrackingProcessor:
            def __init__(self, index: int, should_fail: bool):
                self.index = index
                self.should_fail = should_fail

            def process_template(self, context: TemplateProcessingContext) -> None:
                executed_processors.append(self.index)
                if self.should_fail:
                    raise InvalidTemplateException(f"Processor {self.index} failed")

        processors: List[TemplateProcessor] = [
            TrackingProcessor(i, should_fail=(i == failing_index)) for i in range(num_processors)
        ]
        pipeline = ProcessingPipeline(processors)
        context = TemplateProcessingContext(fragment={"Resources": {}})

        with pytest.raises(InvalidTemplateException) as exc_info:
            pipeline.process_template(context)

        assert f"Processor {failing_index} failed" in str(exc_info.value)

        for i in range(failing_index):
            assert i in executed_processors
        assert failing_index in executed_processors
        for i in range(failing_index + 1, num_processors):
            assert i not in executed_processors

        expected_execution_order = list(range(failing_index + 1))
        assert executed_processors == expected_execution_order
