"""
Template parsing processor for CloudFormation Language Extensions.

This module provides the TemplateParsingProcessor which parses raw template
dictionaries into structured ParsedTemplate objects and validates the
template structure.
"""

from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.models import ParsedTemplate, TemplateProcessingContext


class TemplateParsingProcessor:
    """
    Parses and validates template structure.

    This processor is responsible for:
    - Converting raw template dictionaries into ParsedTemplate objects
    - Initializing missing optional sections as empty dictionaries
    - Validating that the Resources section is not null
    - Validating that no resources or outputs are explicitly set to null

    Requirements:
        - 2.1: Parse valid JSON/YAML template into structured Template object
        - 2.2: Raise InvalidTemplateException when Resources section is null/missing
        - 2.3: Raise InvalidTemplateException when an Output is explicitly null
        - 2.4: Raise InvalidTemplateException when a Resource is explicitly null
        - 2.5: Raise InvalidTemplateException for invalid JSON/YAML syntax
        - 2.6: Initialize missing optional sections as empty dictionaries

    Example:
        >>> processor = TemplateParsingProcessor()
        >>> context = TemplateProcessingContext(
        ...     fragment={"Resources": {"MyBucket": {"Type": "AWS::S3::Bucket"}}}
        ... )
        >>> processor.process_template(context)
        >>> print(context.parsed_template.resources)
        {'MyBucket': {'Type': 'AWS::S3::Bucket'}}
    """

    def process_template(self, context: TemplateProcessingContext) -> None:
        """
        Process the template by parsing and validating it.

        This method parses the template fragment into a ParsedTemplate
        object and validates its structure. The parsed template is
        stored in context.parsed_template.

        Args:
            context: The mutable template processing context containing
                     the template fragment to parse.

        Raises:
            InvalidTemplateException: If the template structure is invalid.
        """
        parsed = self._parse_template(context.fragment)
        self._validate_template(parsed)
        context.parsed_template = parsed

    def _parse_template(self, fragment: Dict[str, Any]) -> ParsedTemplate:
        """
        Convert raw dict to ParsedTemplate.

        This method extracts all standard CloudFormation template sections
        from the raw dictionary and creates a ParsedTemplate object.
        Missing optional sections (Parameters, Conditions, Outputs, Mappings)
        are initialized as empty dictionaries per Requirement 2.6.

        Note: Resources is NOT optional and is NOT converted to empty dict.
        The validation step will check if Resources is null/missing.

        Args:
            fragment: The raw template dictionary.

        Returns:
            A ParsedTemplate object with all sections populated.
        """
        # Get resources without converting None to {} - validation will check this
        resources = fragment.get("Resources")

        return ParsedTemplate(
            aws_template_format_version=fragment.get("AWSTemplateFormatVersion"),
            description=fragment.get("Description"),
            # Optional sections: initialize as empty dict if missing/null (Req 2.6)
            parameters=fragment.get("Parameters") or {},
            mappings=fragment.get("Mappings") or {},
            conditions=fragment.get("Conditions") or {},
            # Resources is required - keep as-is for validation
            resources=resources,
            # Outputs: initialize as empty dict if missing, but preserve None values
            # inside outputs for validation
            outputs=fragment.get("Outputs") or {},
            transform=fragment.get("Transform"),
        )

    def _validate_template(self, template: ParsedTemplate) -> None:
        """
        Validate template structure.

        This method performs structural validation on the parsed template:
        - Ensures the Resources section is not null or missing (Requirement 2.2)
        - Ensures no resource definitions are null (Requirement 2.4)
        - Ensures no output definitions are null (Requirement 2.3)

        Args:
            template: The parsed template to validate.

        Raises:
            InvalidTemplateException: If validation fails.
        """
        # Validate Resources section is not null or missing (Requirement 2.2)
        if template.resources is None:
            raise InvalidTemplateException("The Resources section must not be null")

        # Validate no null resource definitions (Requirement 2.4)
        for logical_id, resource in template.resources.items():
            if resource is None:
                raise InvalidTemplateException(f"[/Resources/{logical_id}] resource definition is malformed")
            # Validate resource is a dictionary or a list (for Fn::ForEach)
            # Fn::ForEach keys have format "Fn::ForEach::LoopName" and values are lists
            if not isinstance(resource, (dict, list)):
                raise InvalidTemplateException(f"[/Resources/{logical_id}] resource definition is malformed")

        # Validate no null output definitions (Requirement 2.3)
        for logical_id, output in template.outputs.items():
            if output is None:
                raise InvalidTemplateException(f"[/Outputs/{logical_id}] 'null' values are not allowed")
