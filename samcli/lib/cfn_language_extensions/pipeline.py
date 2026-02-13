"""
Processing pipeline for CloudFormation Language Extensions.

This module provides the core pipeline infrastructure for processing
CloudFormation templates through a sequence of processors.

The pipeline pattern allows for:
- Ordered execution of template processors
- Exception propagation (stop on first error)
- Extensibility through custom processors
"""

from typing import Any, Dict, List, Protocol, runtime_checkable

from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext


@runtime_checkable
class TemplateProcessor(Protocol):
    """
    Interface for template processors in the pipeline.

    Template processors are components that transform or validate
    CloudFormation templates. Each processor receives a mutable
    context object and modifies it in place.

    Implementations should:
    - Modify the context.fragment or other context fields as needed
    - Raise InvalidTemplateException for validation errors
    - Not catch exceptions from other processors

    Example:
        >>> class MyProcessor:
        ...     def process_template(self, context: TemplateProcessingContext) -> None:
        ...         # Modify context.fragment in place
        ...         context.fragment["Processed"] = True
    """

    def process_template(self, context: TemplateProcessingContext) -> None:
        """
        Process the template, modifying context in place.

        Args:
            context: The mutable template processing context containing
                     the template fragment and processing state.

        Raises:
            InvalidTemplateException: If the template is invalid or
                                      processing fails.
        """
        ...


class ProcessingPipeline:
    """
    Executes a sequence of processors on a template.

    The ProcessingPipeline accepts a list of TemplateProcessor instances
    and executes them in order on a TemplateProcessingContext. Each
    processor modifies the context in place.

    Exception Handling:
        If any processor raises an exception (typically InvalidTemplateException),
        the pipeline stops execution immediately and propagates the exception
        to the caller. Subsequent processors are NOT executed.

    Attributes:
        _processors: The ordered list of processors to execute.

    Example:
        >>> from samcli.lib.cfn_language_extensions.pipeline import ProcessingPipeline
        >>> from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext
        >>>
        >>> # Create processors
        >>> processors = [ParserProcessor(), ResolverProcessor()]
        >>> pipeline = ProcessingPipeline(processors)
        >>>
        >>> # Process a template
        >>> context = TemplateProcessingContext(
        ...     fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}
        ... )
        >>> result = pipeline.process_template(context)

    Requirements:
        - 1.1: Accept a list of Template_Processors and execute them in order
        - 1.2: Pass a Template_Processing_Context through each processor
        - 1.3: Return the processed template fragment after all processors complete
        - 1.4: Propagate exceptions without continuing to subsequent processors
    """

    def __init__(self, processors: List[TemplateProcessor]) -> None:
        """
        Initialize the pipeline with a list of processors.

        Args:
            processors: An ordered list of TemplateProcessor instances.
                        Processors will be executed in the order provided.

        Example:
            >>> pipeline = ProcessingPipeline([
            ...     ParserProcessor(),
            ...     ForEachProcessor(),
            ...     IntrinsicResolver(),
            ... ])
        """
        self._processors = processors

    def process_template(self, context: TemplateProcessingContext) -> Dict[str, Any]:
        """
        Run all processors and return the processed fragment.

        Executes each processor in order, passing the context through
        the pipeline. Each processor modifies the context in place.

        Args:
            context: The template processing context containing the
                     template fragment and processing configuration.

        Returns:
            The processed template fragment as a dictionary.

        Raises:
            InvalidTemplateException: If any processor raises this exception.
                                      The exception is propagated without
                                      executing subsequent processors.

        Example:
            >>> context = TemplateProcessingContext(
            ...     fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}
            ... )
            >>> result = pipeline.process_template(context)
            >>> print(result)
            {'Resources': {'MyBucket': {'Type': 'AWS::S3::Bucket'}}}
        """
        for processor in self._processors:
            processor.process_template(context)
        return context.fragment

    @property
    def processors(self) -> List[TemplateProcessor]:
        """
        Get the list of processors in the pipeline.

        Returns:
            A copy of the processor list to prevent external modification.
        """
        return list(self._processors)
