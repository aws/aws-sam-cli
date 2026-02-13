"""
Public API for CloudFormation Language Extensions processing.

This module provides the main entry point for processing CloudFormation templates
with language extensions. It creates a default processing pipeline with all
necessary processors and resolvers.

The main function `process_template` accepts a template dictionary and optional
processing options, and returns the processed template with language extensions
resolved.

Requirements:
    - 12.1: Provide a process_template function that accepts a template dictionary
    - 12.4: Support loading templates from JSON and YAML files
    - 12.5: Return the processed template as a Python dictionary
"""

import copy
import json
import logging
import os
from typing import Any, Dict, List, Optional

import yaml

from samcli.lib.cfn_language_extensions.exceptions import (
    InvalidTemplateException,
    UnresolvableReferenceError,
)
from samcli.lib.cfn_language_extensions.models import (
    PseudoParameterValues,
    ResolutionMode,
    TemplateProcessingContext,
)
from samcli.lib.cfn_language_extensions.pipeline import ProcessingPipeline, TemplateProcessor
from samcli.lib.cfn_language_extensions.processors import (
    DeletionPolicyProcessor,
    ForEachProcessor,
    TemplateParsingProcessor,
    UpdateReplacePolicyProcessor,
)
from samcli.lib.cfn_language_extensions.resolvers import (
    ConditionResolver,
    FnBase64Resolver,
    FnFindInMapResolver,
    FnIfResolver,
    FnJoinResolver,
    FnLengthResolver,
    FnRefResolver,
    FnSelectResolver,
    FnSplitResolver,
    FnSubResolver,
    FnToJsonStringResolver,
    IntrinsicResolver,
)

LOG = logging.getLogger(__name__)


def create_default_intrinsic_resolver(context: TemplateProcessingContext) -> IntrinsicResolver:
    """
    Create an IntrinsicResolver with all standard resolvers registered.

    This function creates an IntrinsicResolver instance and registers all
    the standard intrinsic function resolvers in the correct order for
    proper resolution.

    Args:
        context: The template processing context.

    Returns:
        An IntrinsicResolver with all standard resolvers registered.
    """
    resolver = IntrinsicResolver(context)

    # Register resolvers in order of dependency
    # Condition-related resolvers first (needed by Fn::If)
    resolver.register_resolver(ConditionResolver)
    resolver.register_resolver(FnIfResolver)

    # Basic resolvers
    resolver.register_resolver(FnRefResolver)
    resolver.register_resolver(FnBase64Resolver)

    # String manipulation resolvers
    resolver.register_resolver(FnJoinResolver)
    resolver.register_resolver(FnSplitResolver)
    resolver.register_resolver(FnSubResolver)

    # List/collection resolvers
    resolver.register_resolver(FnSelectResolver)
    resolver.register_resolver(FnLengthResolver)

    # Map lookup resolver
    resolver.register_resolver(FnFindInMapResolver)

    # JSON conversion resolver
    resolver.register_resolver(FnToJsonStringResolver)

    return resolver


class IntrinsicResolverProcessor:
    """
    Processor that resolves intrinsic functions in the template.

    This processor wraps an IntrinsicResolver and applies it to the
    template fragment, resolving all intrinsic functions that can be
    resolved locally.

    Note: The Conditions section is handled specially - condition intrinsics
    (Fn::Equals, Fn::And, Fn::Or, Fn::Not) are NOT resolved to boolean values.
    They are only resolved when evaluating Fn::If. This matches the Kotlin
    implementation behavior.
    """

    def __init__(self, intrinsic_resolver: IntrinsicResolver) -> None:
        """
        Initialize the processor with an intrinsic resolver.

        Args:
            intrinsic_resolver: The IntrinsicResolver to use for resolution.
        """
        self._resolver = intrinsic_resolver

    def process_template(self, context: TemplateProcessingContext) -> None:
        """
        Process the template by resolving intrinsic functions.

        This method walks through the template fragment and resolves
        all intrinsic functions that can be resolved locally.

        The Conditions section is handled specially - condition intrinsics
        are preserved and not resolved to boolean values.

        Resources and Outputs with false conditions use partial resolution
        where unresolvable intrinsics are replaced with AWS::NoValue instead
        of throwing errors.

        After resolution, properties with AWS::NoValue are removed.

        Args:
            context: The template processing context.
        """
        # Process each section separately to handle Conditions specially
        fragment = context.fragment

        # Pre-evaluate all conditions to detect circular dependencies
        # Use fragment's conditions (which may have been expanded by ForEach)
        # instead of parsed_template's conditions
        if "Conditions" in fragment and fragment["Conditions"]:
            self._pre_evaluate_conditions(context, fragment["Conditions"])

        # Validate resource conditions reference valid conditions
        self._validate_resource_conditions(context, fragment)

        # Process Conditions section without resolving condition intrinsics
        if "Conditions" in fragment:
            fragment["Conditions"] = self._resolve_conditions_section(fragment["Conditions"])

        # Process Resources section with special handling for false conditions
        if "Resources" in fragment:
            fragment["Resources"] = self._resolve_resources_section(fragment["Resources"], context)

        # Process Outputs section with special handling for false conditions
        if "Outputs" in fragment:
            fragment["Outputs"] = self._resolve_outputs_section(fragment["Outputs"], context)

        # Process other sections normally
        for key in list(fragment.keys()):
            if key not in ("Conditions", "Resources", "Outputs"):
                fragment[key] = self._resolver.resolve_value(fragment[key])

        # Remove AWS::NoValue references from Resources (but preserve policy attrs)
        if "Resources" in fragment:
            fragment["Resources"] = self._remove_no_value(fragment["Resources"])

        context.fragment = fragment

    def _resolve_resources_section(self, resources: Any, context: TemplateProcessingContext) -> Any:
        """
        Resolve intrinsic functions in the Resources section.

        Resources with false conditions use partial resolution where
        unresolvable intrinsics are replaced with AWS::NoValue.

        Args:
            resources: The Resources section dictionary.
            context: The template processing context.

        Returns:
            The Resources section with intrinsics resolved.
        """
        if not isinstance(resources, dict):
            return self._resolver.resolve_value(resources)

        result = {}
        for logical_id, resource in resources.items():
            if isinstance(resource, dict) and "Condition" in resource:
                condition_name = resource["Condition"]
                # Check if condition is false
                if condition_name in context.resolved_conditions:
                    if not context.resolved_conditions[condition_name]:
                        # False condition - use partial resolution
                        result[logical_id] = self._resolve_with_false_condition(resource)
                        continue
            # Normal resolution
            result[logical_id] = self._resolver.resolve_value(resource)
        return result

    def _resolve_outputs_section(self, outputs: Any, context: TemplateProcessingContext) -> Any:
        """
        Resolve intrinsic functions in the Outputs section.

        Outputs with false conditions use partial resolution where
        unresolvable intrinsics are replaced with AWS::NoValue.

        Args:
            outputs: The Outputs section dictionary.
            context: The template processing context.

        Returns:
            The Outputs section with intrinsics resolved.
        """
        if not isinstance(outputs, dict):
            return self._resolver.resolve_value(outputs)

        result = {}
        for logical_id, output in outputs.items():
            if isinstance(output, dict) and "Condition" in output:
                condition_name = output["Condition"]
                # Check if condition is false
                if condition_name in context.resolved_conditions:
                    if not context.resolved_conditions[condition_name]:
                        # False condition - use partial resolution
                        result[logical_id] = self._resolve_with_false_condition(output)
                        continue
            # Normal resolution
            result[logical_id] = self._resolver.resolve_value(output)
        return result

    def _resolve_with_false_condition(self, value: Any) -> Any:
        """
        Resolve a value using partial resolution for false conditions.

        In this mode, unresolvable intrinsics are replaced with AWS::NoValue
        instead of throwing errors.

        Args:
            value: The value to resolve.

        Returns:
            The resolved value with unresolvable intrinsics replaced by AWS::NoValue.
        """
        return self._partial_resolve(value)

    def _partial_resolve(self, value: Any) -> Any:
        """
        Partially resolve a value, replacing unresolvable intrinsics with AWS::NoValue.

        This is used for resources/outputs with false conditions where we want to
        preserve the structure but replace unresolvable parts with AWS::NoValue.

        For false-condition resources, Refs to parameters are also replaced with
        AWS::NoValue (even if they have default values) to match Kotlin behavior.

        Args:
            value: The value to partially resolve.

        Returns:
            The partially resolved value.
        """
        if isinstance(value, dict):
            if len(value) == 1:
                key = next(iter(value.keys()))
                inner_value = value[key]

                # Check if this is an intrinsic function
                if key == "Ref":
                    # For false-condition resources, replace Refs to parameters with AWS::NoValue
                    # Only keep Refs to pseudo-parameters that are always available
                    always_available_refs = {
                        "AWS::NoValue",
                        "AWS::Region",
                        "AWS::AccountId",
                        "AWS::StackName",
                        "AWS::StackId",
                        "AWS::Partition",
                        "AWS::URLSuffix",
                    }
                    if isinstance(inner_value, str) and inner_value not in always_available_refs:
                        return {"Ref": "AWS::NoValue"}
                    # Try to resolve pseudo-parameters
                    try:
                        return self._resolver.resolve_value(value)
                    except (InvalidTemplateException, UnresolvableReferenceError, KeyError, ValueError, TypeError):
                        return {"Ref": "AWS::NoValue"}

                elif key.startswith("Fn::") or key == "Condition":
                    # Try to resolve it
                    try:
                        return self._resolver.resolve_value(value)
                    except (InvalidTemplateException, UnresolvableReferenceError, KeyError, ValueError, TypeError):
                        # Can't resolve - replace unresolvable parts with AWS::NoValue
                        if key == "Fn::FindInMap":
                            # FindInMap - try to partially resolve arguments
                            return self._partial_resolve_find_in_map(value)
                        elif key == "Fn::ToJsonString":
                            # ToJsonString - replace with AWS::NoValue if can't resolve
                            return {"Ref": "AWS::NoValue"}
                        else:
                            # Other intrinsics - try to partially resolve arguments
                            resolved_inner = self._partial_resolve(inner_value)
                            return {key: resolved_inner}

            # Regular dict - recursively resolve values
            return {k: self._partial_resolve(v) for k, v in value.items()}

        elif isinstance(value, list):
            return [self._partial_resolve(item) for item in value]

        # Primitive value - return as-is
        return value

    def _partial_resolve_find_in_map(self, value: Dict[str, Any]) -> Any:
        """
        Partially resolve Fn::FindInMap, replacing unresolvable parts with AWS::NoValue.

        For false-condition resources, Refs to parameters in FindInMap arguments
        are replaced with AWS::NoValue. However, string literals that don't exist
        in the mappings still throw errors.

        Args:
            value: The Fn::FindInMap intrinsic function.

        Returns:
            The partially resolved FindInMap or the resolved value.
        """
        from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException

        args = value.get("Fn::FindInMap", [])
        if not isinstance(args, list) or len(args) < 3:
            return value

        # Partially resolve each argument (this will replace Refs to params with AWS::NoValue)
        resolved_args = []
        for i, arg in enumerate(args):
            resolved = self._partial_resolve(arg)
            resolved_args.append(resolved)

        # Check if any of the first 3 args are AWS::NoValue
        has_no_value = any(
            isinstance(a, dict) and a.get("Ref") == "AWS::NoValue"
            for a in resolved_args[:3]  # Only check map name, top key, second key
        )

        if has_no_value:
            # Can't resolve - return with partially resolved args
            return {"Fn::FindInMap": resolved_args}

        # All args are resolved to strings - validate they exist in mappings
        # If they're string literals that don't exist, throw an error
        map_name = resolved_args[0]
        top_key = resolved_args[1]
        second_key = resolved_args[2]

        if isinstance(map_name, str) and isinstance(top_key, str) and isinstance(second_key, str):
            # All keys are strings - try to do the lookup
            # This will throw an error if the keys don't exist
            try:
                result = self._resolver.resolve_value({"Fn::FindInMap": resolved_args})
                return result
            except InvalidTemplateException:
                # Re-raise - string literals that don't exist should error
                raise
            except Exception:
                # Other errors - return with partially resolved args
                return {"Fn::FindInMap": resolved_args}

        # Some args are not strings - return with partially resolved args
        return {"Fn::FindInMap": resolved_args}

    def _validate_resource_conditions(self, context: TemplateProcessingContext, fragment: Dict[str, Any]) -> None:
        """
        Validate that resource Condition attributes reference valid conditions.

        Args:
            context: The template processing context.
            fragment: The template fragment.

        Raises:
            InvalidTemplateException: If a resource references a non-existent condition.
        """
        from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException

        resources = fragment.get("Resources", {})
        conditions = fragment.get("Conditions", {})

        if not isinstance(resources, dict):
            return

        for logical_id, resource in resources.items():
            if isinstance(resource, dict) and "Condition" in resource:
                condition_name = resource["Condition"]
                if isinstance(condition_name, str):
                    # Check if condition exists
                    if not conditions or condition_name not in conditions:
                        raise InvalidTemplateException(
                            f"Resource '{logical_id}' references non-existent condition '{condition_name}'"
                        )

    def _pre_evaluate_conditions(self, context: TemplateProcessingContext, conditions: Dict[str, Any]) -> None:
        """
        Pre-evaluate all conditions to detect circular dependencies.

        This method first checks for circular dependencies using graph traversal,
        then evaluates all conditions to populate the resolved_conditions cache.

        Args:
            context: The template processing context.
            conditions: The conditions dictionary from the fragment.

        Raises:
            InvalidTemplateException: If circular condition dependencies are detected.
        """
        from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException

        # Update parsed_template conditions to match fragment (for ForEach expansion)
        if context.parsed_template:
            context.parsed_template.conditions = conditions

        # Build dependency graph
        dependencies = {}
        for condition_name, condition_def in conditions.items():
            dependencies[condition_name] = self._extract_condition_dependencies(condition_def)

        # Detect cycles using DFS
        visited = set()
        rec_stack = set()

        def detect_cycle(node, path):
            """DFS to detect cycles, returns the cycle path if found."""
            if node in rec_stack:
                # Found a cycle - return the path from the cycle start
                cycle_start = path.index(node)
                return path[cycle_start:]
            if node in visited:
                return None

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for dep in dependencies.get(node, []):
                if dep in conditions:  # Only check conditions that exist
                    cycle = detect_cycle(dep, path)
                    if cycle:
                        return cycle

            path.pop()
            rec_stack.remove(node)
            return None

        # Check each condition for cycles
        for condition_name in conditions:
            visited.clear()
            rec_stack.clear()
            cycle = detect_cycle(condition_name, [])
            if cycle:
                # Format error message like Kotlin: "Found circular condition dependency between X and Y"
                if len(cycle) >= 2:
                    raise InvalidTemplateException(
                        f"Found circular condition dependency between {cycle[0]} and {cycle[1]}"
                    )
                else:
                    raise InvalidTemplateException(
                        f"Found circular condition dependency between {cycle[0]} and {cycle[0]}"
                    )

        # Now evaluate all conditions (no cycles, so this is safe)
        for condition_name in conditions:
            if condition_name not in context.resolved_conditions:
                try:
                    self._resolver.resolve_value({"Condition": condition_name})
                except InvalidTemplateException:
                    raise

    def _extract_condition_dependencies(self, value: Any) -> set:
        """
        Extract all condition references from a condition definition.

        Args:
            value: The condition definition to analyze.

        Returns:
            A set of condition names that this definition depends on.
        """
        dependencies = set()

        if isinstance(value, dict):
            if len(value) == 1:
                key = next(iter(value.keys()))
                if key == "Condition":
                    # Direct condition reference
                    ref = value[key]
                    if isinstance(ref, str):
                        dependencies.add(ref)
                else:
                    # Recurse into the value
                    dependencies.update(self._extract_condition_dependencies(value[key]))
            else:
                for v in value.values():
                    dependencies.update(self._extract_condition_dependencies(v))
        elif isinstance(value, list):
            for item in value:
                dependencies.update(self._extract_condition_dependencies(item))

        return dependencies

    def _remove_no_value(self, value: Any, preserve_policy_attrs: bool = True) -> Any:
        """
        Remove properties that have AWS::NoValue as their value.

        AWS::NoValue is a pseudo-parameter that indicates a property should
        be removed from the template. When Fn::If returns AWS::NoValue,
        the resolver returns None.

        Note: DeletionPolicy and UpdateReplacePolicy attributes are preserved
        even if they are AWS::NoValue, so that the policy processors can
        validate them and raise appropriate errors.

        Note: AWS::NoValue is NOT removed from intrinsic function arguments
        (e.g., Fn::FindInMap, Fn::Join) as it may be intentionally placed there
        for false-condition resources.

        Args:
            value: The value to process.
            preserve_policy_attrs: If True, preserve DeletionPolicy and
                                   UpdateReplacePolicy even if AWS::NoValue.

        Returns:
            The value with AWS::NoValue properties removed.
        """
        # Policy attributes that should not be removed even if AWS::NoValue
        POLICY_ATTRS = {"DeletionPolicy", "UpdateReplacePolicy"}
        # Intrinsic functions whose arguments should preserve AWS::NoValue
        INTRINSIC_FUNCTIONS = {
            "Fn::FindInMap",
            "Fn::Join",
            "Fn::Select",
            "Fn::Split",
            "Fn::Sub",
            "Fn::If",
            "Fn::And",
            "Fn::Or",
            "Fn::Not",
            "Fn::Equals",
            "Fn::GetAtt",
            "Fn::GetAZs",
            "Fn::ImportValue",
            "Fn::Length",
            "Fn::ToJsonString",
            "Fn::Base64",
            "Fn::Cidr",
            "Fn::ForEach",
            "Ref",
            "Condition",
        }

        if isinstance(value, dict):
            # Check if this is an intrinsic function - if so, preserve AWS::NoValue in args
            if len(value) == 1:
                key = next(iter(value.keys()))
                if key in INTRINSIC_FUNCTIONS:
                    # This is an intrinsic function - preserve AWS::NoValue in arguments
                    inner = value[key]
                    if isinstance(inner, list):
                        # Recursively process but don't filter out AWS::NoValue
                        return {key: [self._remove_no_value(item, preserve_policy_attrs) for item in inner]}
                    elif isinstance(inner, dict):
                        return {key: self._remove_no_value(inner, preserve_policy_attrs)}
                    else:
                        return value

            result = {}
            for k, v in value.items():
                # Preserve policy attributes for validation by policy processors
                if preserve_policy_attrs and k in POLICY_ATTRS:
                    result[k] = self._remove_no_value(v, preserve_policy_attrs=False)
                    continue
                # Check if value is {"Ref": "AWS::NoValue"} or None
                if self._is_no_value(v) or v is None:
                    continue  # Skip this property
                result[k] = self._remove_no_value(v, preserve_policy_attrs)
            return result
        elif isinstance(value, list):
            # Filter out AWS::NoValue and None from lists (but not intrinsic args - handled above)
            return [
                self._remove_no_value(item, preserve_policy_attrs)
                for item in value
                if not self._is_no_value(item) and item is not None
            ]
        return value

    def _is_no_value(self, value: Any) -> bool:
        """
        Check if a value is {"Ref": "AWS::NoValue"}.

        Args:
            value: The value to check.

        Returns:
            True if the value is AWS::NoValue, False otherwise.
        """
        if isinstance(value, dict) and len(value) == 1:
            if "Ref" in value and value["Ref"] == "AWS::NoValue":
                return True
        return False

    def _resolve_conditions_section(self, conditions: Any) -> Any:
        """
        Resolve intrinsic functions in the Conditions section.

        This method resolves intrinsics like Ref, Fn::Sub, etc. but
        preserves condition intrinsics (Fn::Equals, Fn::And, Fn::Or, Fn::Not)
        without evaluating them to boolean values.

        Args:
            conditions: The Conditions section dictionary.

        Returns:
            The Conditions section with non-condition intrinsics resolved.
        """
        if not isinstance(conditions, dict):
            return conditions

        result = {}
        for condition_name, condition_def in conditions.items():
            result[condition_name] = self._resolve_condition_value(condition_def)
        return result

    def _resolve_condition_value(self, value: Any) -> Any:
        """
        Resolve a value within the Conditions section.

        Condition intrinsics (Fn::Equals, Fn::And, Fn::Or, Fn::Not, Condition)
        are preserved but their arguments are resolved.

        Args:
            value: The value to resolve.

        Returns:
            The resolved value with condition intrinsics preserved.
        """
        if isinstance(value, dict):
            if len(value) == 1:
                key = next(iter(value.keys()))
                args = value[key]

                # Condition intrinsics - preserve but resolve arguments
                if key in ("Fn::Equals", "Fn::And", "Fn::Or", "Fn::Not", "Condition"):
                    if key == "Condition":
                        # Condition references are kept as-is
                        return value
                    else:
                        # Resolve arguments but keep the intrinsic structure
                        resolved_args = self._resolve_condition_value(args)
                        return {key: resolved_args}
                else:
                    # Other intrinsics (Ref, Fn::Sub, etc.) - resolve normally
                    return self._resolver.resolve_value(value)
            else:
                # Multiple keys - resolve each value
                return {k: self._resolve_condition_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_condition_value(item) for item in value]
        else:
            # Primitives - return as-is
            return value


def create_default_pipeline(context: TemplateProcessingContext) -> ProcessingPipeline:
    """
    Create a default processing pipeline with all standard processors.

    The default pipeline includes:
    1. TemplateParsingProcessor - Parses and validates template structure
    2. ForEachProcessor - Expands Fn::ForEach loops
    3. IntrinsicResolverProcessor - Resolves intrinsic functions
    4. DeletionPolicyProcessor - Validates and resolves DeletionPolicy
    5. UpdateReplacePolicyProcessor - Validates and resolves UpdateReplacePolicy

    Args:
        context: The template processing context.

    Returns:
        A ProcessingPipeline with all standard processors configured.
    """
    # Create the intrinsic resolver
    intrinsic_resolver = create_default_intrinsic_resolver(context)

    # Create processors in order
    processors: List[TemplateProcessor] = [
        TemplateParsingProcessor(),
        ForEachProcessor(intrinsic_resolver=intrinsic_resolver),
        IntrinsicResolverProcessor(intrinsic_resolver),
        DeletionPolicyProcessor(),
        UpdateReplacePolicyProcessor(),
    ]

    return ProcessingPipeline(processors)


def process_template(
    template: Dict[str, Any],
    parameter_values: Optional[Dict[str, Any]] = None,
    pseudo_parameters: Optional[PseudoParameterValues] = None,
    resolution_mode: ResolutionMode = ResolutionMode.PARTIAL,
) -> Dict[str, Any]:
    """
    Process a CloudFormation template with language extensions.

    This is the main entry point for processing CloudFormation templates.
    It creates a default processing pipeline and runs the template through
    all processors to resolve language extensions.

    The function:
    1. Creates a TemplateProcessingContext with the provided options
    2. Creates a default pipeline with all standard processors
    3. Processes the template through the pipeline
    4. Returns the processed template as a dictionary

    Args:
        template: The CloudFormation template as a dictionary.
        parameter_values: Optional dictionary of parameter values to use
                          for resolving Ref to parameters.
        pseudo_parameters: Optional PseudoParameterValues for resolving
                           AWS pseudo-parameters (AWS::Region, etc.).
        resolution_mode: How to handle unresolvable references.
                         PARTIAL (default): Preserve unresolvable refs.
                         FULL: Raise error on unresolvable refs.

    Returns:
        The processed template as a dictionary with language extensions
        resolved.

    Raises:
        InvalidTemplateException: If the template is invalid or processing
                                  fails.

    Example:
        >>> template = {
        ...     "Resources": {
        ...         "Fn::ForEach::Topics": [
        ...             "TopicName",
        ...             ["Alerts", "Notifications"],
        ...             {"Topic${TopicName}": {"Type": "AWS::SNS::Topic"}}
        ...         ]
        ...     }
        ... }
        >>> result = process_template(template)
        >>> print(result["Resources"])
        {'TopicAlerts': {'Type': 'AWS::SNS::Topic'},
         'TopicNotifications': {'Type': 'AWS::SNS::Topic'}}

    Requirements:
        - 12.1: Accept a template dictionary and processing options
        - 12.4: Support both JSON and YAML template input formats
        - 12.5: Return the processed template as a Python dictionary
    """
    # Create the processing context
    context = TemplateProcessingContext(
        fragment=copy.deepcopy(template),
        parameter_values=parameter_values or {},
        pseudo_parameters=pseudo_parameters,
        resolution_mode=resolution_mode,
    )

    # Create and run the default pipeline
    pipeline = create_default_pipeline(context)
    return pipeline.process_template(context)


def load_template_from_json(file_path: str) -> Dict[str, Any]:
    """
    Load a CloudFormation template from a JSON file.

    This function reads a JSON file and parses it into a dictionary
    suitable for processing with the process_template function.

    Args:
        file_path: Path to the JSON template file.

    Returns:
        The template as a Python dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        IsADirectoryError: If the path points to a directory.

    Example:
        >>> template = load_template_from_json("template.json")
        >>> result = process_template(template)

    Requirements:
        - 12.4: Support loading templates from JSON files
    """
    with open(file_path, "r", encoding="utf-8") as f:
        result = json.load(f)
        return dict(result) if isinstance(result, dict) else {}


def load_template_from_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load a CloudFormation template from a YAML file.

    This function reads a YAML file and parses it into a dictionary
    suitable for processing with the process_template function.

    CloudFormation templates often use YAML format for better readability,
    especially when using multi-line strings or complex nested structures.

    Args:
        file_path: Path to the YAML template file.

    Returns:
        The template as a Python dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
        IsADirectoryError: If the path points to a directory.

    Example:
        >>> template = load_template_from_yaml("template.yaml")
        >>> result = process_template(template)

    Requirements:
        - 12.4: Support loading templates from YAML files
    """
    with open(file_path, "r", encoding="utf-8") as f:
        result = yaml.safe_load(f)
        return dict(result) if isinstance(result, dict) else {}


def load_template(file_path: str) -> Dict[str, Any]:
    """
    Load a CloudFormation template from a file, auto-detecting the format.

    This function automatically detects the file format based on the file
    extension and loads the template accordingly:
    - .json files are loaded as JSON
    - .yaml, .yml, and .template files are loaded as YAML

    Args:
        file_path: Path to the template file.

    Returns:
        The template as a Python dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is not recognized.
        json.JSONDecodeError: If a JSON file contains invalid JSON.
        yaml.YAMLError: If a YAML file contains invalid YAML.
        IsADirectoryError: If the path points to a directory.

    Example:
        >>> # Auto-detects JSON format
        >>> template = load_template("template.json")
        >>>
        >>> # Auto-detects YAML format
        >>> template = load_template("template.yaml")
        >>>
        >>> result = process_template(template)

    Requirements:
        - 12.4: Support loading templates from JSON and YAML files
    """
    # Get the file extension (lowercase for case-insensitive comparison)
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == ".json":
        return load_template_from_json(file_path)
    elif ext in (".yaml", ".yml", ".template"):
        return load_template_from_yaml(file_path)
    else:
        raise ValueError(
            f"Unrecognized file extension '{ext}'. " f"Supported extensions are: .json, .yaml, .yml, .template"
        )
