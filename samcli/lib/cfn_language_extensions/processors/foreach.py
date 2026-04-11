"""
ForEach processor for CloudFormation Language Extensions.

This module provides the ForEachProcessor which handles Fn::ForEach loops
in CloudFormation templates. Fn::ForEach allows generating multiple resources,
conditions, or outputs from a template, reducing duplication.

The processor handles:
- Detection of Fn::ForEach:: prefixed keys in Resources, Outputs, and Conditions
- Validation of ForEach structure (identifier, collection, body)
- Resolution of collections containing intrinsic functions
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext
from samcli.lib.cfn_language_extensions.utils import FOREACH_PREFIX, is_foreach_key

LOG = logging.getLogger(__name__)

# Pre-compiled pattern for SSM/Secrets Manager dynamic references: {{resolve:service:reference}}
_DYNAMIC_REF_PATTERN = re.compile(r"\{\{resolve:(ssm|ssm-secure|secretsmanager):[^}]+\}\}", re.IGNORECASE)


class ForEachProcessor:
    """
    Expands Fn::ForEach loops in Resources, Outputs, and Conditions sections.

    Fn::ForEach is a CloudFormation language extension that allows generating
    multiple resources, conditions, or outputs from a single template definition.
    The syntax is:

        "Fn::ForEach::UniqueLoopName": [
            "Identifier",
            ["Item1", "Item2", ...],
            {
                "OutputKey${Identifier}": { ... template body ... }
            }
        ]

    This processor:
    1. Detects Fn::ForEach:: prefixed keys in supported sections
    2. Validates the ForEach structure (identifier, collection, body)
    3. Validates nesting depth does not exceed the maximum allowed (5 levels)
    4. Resolves collections that contain intrinsic functions

    """

    MAX_FOREACH_NESTING_DEPTH = 5
    _LAYOUT_ERROR_FMT = "{} layout is incorrect"

    def __init__(self, intrinsic_resolver: Optional[Any] = None) -> None:
        """
        Initialize the ForEachProcessor.

        Args:
            intrinsic_resolver: Optional IntrinsicResolver instance for resolving
                                collections that contain intrinsic functions.
                                If None, collections with intrinsics will not be
                                resolved (useful for validation-only scenarios).
        """
        self._intrinsic_resolver = intrinsic_resolver

    def _merge_expanded(
        self,
        result: Dict[str, Any],
        expanded: Dict[str, Any],
        foreach_key: str,
    ) -> None:
        """
        Merge expanded ForEach entries into result, raising on key collisions.

        Args:
            result: The target dictionary to merge into (mutated in place).
            expanded: The expanded ForEach entries to merge.
            foreach_key: The ForEach key that produced the expansion (for error messages).

        Raises:
            InvalidTemplateException: If any expanded key already exists in result.
        """
        collisions = result.keys() & expanded.keys()
        if collisions:
            collision_list = ", ".join(sorted(collisions))
            raise InvalidTemplateException(
                f"Fn::ForEach expansion in '{foreach_key}' produced logical IDs that "
                f"conflict with existing entries: {collision_list}"
            )
        result.update(expanded)

    def process_template(self, context: TemplateProcessingContext) -> None:
        """
        Process the template by validating and preparing Fn::ForEach constructs.

        This method scans the Conditions, Resources, and Outputs sections for
        Fn::ForEach:: prefixed keys and validates their structure. Collections
        containing intrinsic functions are resolved if an intrinsic_resolver
        is available.

        Also handles Fn::ForEach within resource Properties sections.

        If a section becomes empty after ForEach expansion (e.g., empty collection),
        the section is removed from the template.

        Args:
            context: The mutable template processing context containing
                     the template fragment to process.

        Raises:
            InvalidTemplateException: If any ForEach construct has invalid structure,
                                      or if nesting depth exceeds the maximum allowed.
        """
        # Validate nesting depth before processing
        self._validate_foreach_nesting_depth(context.fragment)
        LOG.debug("Processing Fn::ForEach constructs in template")

        # Process conditions first (they may be referenced by resources)
        if "Conditions" in context.fragment:
            processed = self._process_section(context.fragment.get("Conditions", {}), context)
            if processed:
                context.fragment["Conditions"] = processed
            else:
                # Remove empty Conditions section
                del context.fragment["Conditions"]

        # Process resources (including ForEach within Properties)
        if "Resources" in context.fragment:
            context.fragment["Resources"] = self._process_resources_section(
                context.fragment.get("Resources", {}), context
            )

        # Process outputs
        if "Outputs" in context.fragment:
            processed = self._process_section(context.fragment.get("Outputs", {}), context)
            if processed:
                context.fragment["Outputs"] = processed
            else:
                # Remove empty Outputs section
                del context.fragment["Outputs"]

    def _process_resources_section(self, section: Any, context: TemplateProcessingContext) -> Any:
        """
        Process the Resources section for Fn::ForEach constructs.

        This handles both:
        1. Top-level ForEach that generates multiple resources
        2. ForEach within resource Properties that generates multiple properties

        Args:
            section: The Resources section dictionary to process.
            context: The template processing context.

        Returns:
            The processed Resources section with ForEach constructs expanded.
        """
        if not isinstance(section, dict):
            return section

        result: Dict[str, Any] = {}

        for key, value in section.items():
            if is_foreach_key(key):
                # Top-level ForEach - generates multiple resources
                identifiers, resolved_collection = self._validate_and_resolve_foreach(key, value, context)
                expanded = self._expand_foreach(key, value, context, None, identifiers, resolved_collection)
                # Process each expanded resource for nested ForEach in Properties
                processed_expanded = {}
                for res_key, res_value in expanded.items():
                    if isinstance(res_value, dict) and "Properties" in res_value:
                        processed_resource = dict(res_value)
                        processed_resource["Properties"] = self._process_section(res_value["Properties"], context)
                        processed_expanded[res_key] = processed_resource
                    else:
                        processed_expanded[res_key] = res_value
                self._merge_expanded(result, processed_expanded, key)
            # Regular resource - check for ForEach in Properties
            elif isinstance(value, dict) and "Properties" in value:
                processed_resource = dict(value)
                processed_resource["Properties"] = self._process_section(value["Properties"], context)
                result[key] = processed_resource
            else:
                result[key] = value

        return result

    def _process_section(
        self,
        section: Any,
        context: TemplateProcessingContext,
        parent_identifiers: Optional[List[str]] = None,
    ) -> Any:
        """
        Process a template section (or nested dict) for Fn::ForEach constructs.

        This method iterates through the section, validates any
        Fn::ForEach:: prefixed keys found, and expands them.
        Used for top-level sections (Resources, Conditions, Outputs),
        resource Properties, and nested ForEach bodies.

        Args:
            section: The dictionary to process.
            context: The template processing context.
            parent_identifiers: List of identifiers from parent ForEach loops (for conflict detection).

        Returns:
            The processed dictionary with ForEach constructs expanded.

        Raises:
            InvalidTemplateException: If any ForEach construct is invalid.
        """
        if not isinstance(section, dict):
            return section

        result: Dict[str, Any] = {}

        for key, value in section.items():
            if is_foreach_key(key):
                identifiers, resolved_collection = self._validate_and_resolve_foreach(
                    key, value, context, parent_identifiers
                )
                expanded = self._expand_foreach(
                    key, value, context, parent_identifiers, identifiers, resolved_collection
                )
                self._merge_expanded(result, expanded, key)
            else:
                result[key] = value

        return result

    def _validate_foreach_nesting_depth(self, template: Dict[str, Any]) -> None:
        """
        Validate that Fn::ForEach nesting does not exceed the maximum allowed depth.

        CloudFormation enforces a maximum nesting depth of 5 for Fn::ForEach loops.
        This method validates the template before processing to provide early feedback.

        Args:
            template: The template dictionary to validate.

        Raises:
            InvalidTemplateException: If the nesting depth exceeds the maximum allowed.
        """
        # Check all sections that can contain Fn::ForEach
        max_depth = 0
        for section_name in ("Resources", "Conditions", "Outputs"):
            section = template.get(section_name, {})
            if isinstance(section, dict):
                section_depth = self._calculate_max_foreach_depth(section, current_depth=0)
                max_depth = max(max_depth, section_depth)

        if max_depth > self.MAX_FOREACH_NESTING_DEPTH:
            raise InvalidTemplateException(
                f"Fn::ForEach nesting depth of {max_depth} exceeds the maximum allowed depth "
                f"of {self.MAX_FOREACH_NESTING_DEPTH}. CloudFormation supports up to "
                f"{self.MAX_FOREACH_NESTING_DEPTH} nested Fn::ForEach loops."
            )

    def _calculate_max_foreach_depth(self, node: Any, current_depth: int) -> int:
        """
        Recursively calculate the maximum Fn::ForEach nesting depth.

        This method traverses the template structure to find the maximum depth
        of nested Fn::ForEach loops.

        Args:
            node: The current node in the template structure to analyze.
            current_depth: The current nesting depth (0 at the top level).

        Returns:
            The maximum nesting depth found in this subtree.
        """
        if isinstance(node, dict):
            max_child_depth = current_depth
            for key, value in node.items():
                if is_foreach_key(key):
                    # Found a ForEach - increment depth and check its body
                    # The body is the third element of the ForEach array
                    if isinstance(value, list) and len(value) >= 3:
                        foreach_body = value[2]
                        child_depth = self._calculate_max_foreach_depth(foreach_body, current_depth + 1)
                        max_child_depth = max(max_child_depth, child_depth)
                    else:
                        # Invalid ForEach structure - just count this level
                        max_child_depth = max(max_child_depth, current_depth + 1)
                else:
                    # Not a ForEach key - recurse into the value
                    child_depth = self._calculate_max_foreach_depth(value, current_depth)
                    max_child_depth = max(max_child_depth, child_depth)
            return max_child_depth
        elif isinstance(node, list):
            if not node:
                return current_depth
            return max(self._calculate_max_foreach_depth(item, current_depth) for item in node)
        else:
            # Primitive value - return current depth
            return current_depth

    def _validate_and_resolve_foreach(
        self, key: str, value: Any, context: TemplateProcessingContext, parent_identifiers: Optional[List[str]] = None
    ) -> Tuple[List[str], List[Any]]:
        """
        Validate a Fn::ForEach construct.

        The ForEach value must be a list with exactly 3 elements:
        1. identifier: A non-empty string OR a list of non-empty strings (for list-of-lists)
                       Can contain intrinsics like {"Ref": "ParamName"}
        2. collection: A list of values to iterate over (or an intrinsic that resolves to a list)
                       For list-of-lists, items can also contain intrinsics
        3. template_body: A dictionary containing the template to expand

        For list-of-lists format:
        - identifier is a list like ["LogicalId", "TopicId"]
        - collection is a list of lists like [[1, "1"], [2, "2"]]
        - Each inner list provides values for the corresponding identifiers

        Args:
            key: The ForEach key (e.g., "Fn::ForEach::Topics").
            value: The ForEach value (should be a 3-element list).
            context: The template processing context.
            parent_identifiers: List of identifiers from parent ForEach loops (for conflict detection).

        Returns:
            A tuple of (identifiers, resolved_collection).

        Raises:
            InvalidTemplateException: If the ForEach structure is invalid.
        """
        if parent_identifiers is None:
            parent_identifiers = []

        # Value must be a list
        if not isinstance(value, list):
            raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))

        # Must have exactly 3 elements
        if len(value) != 3:
            raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))

        identifier = value[0]
        collection = value[1]
        template_body = value[2]

        # Resolve and validate identifier
        identifiers = self._resolve_identifiers(identifier, context)
        if not identifiers:
            raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))

        # Check for identifier conflicts with parameter names
        for ident in identifiers:
            self._check_identifier_conflicts(ident, key, context, parent_identifiers)

        # Check for loop name conflicts with parameter names
        loop_name = self.get_foreach_loop_name(key)
        parameter_names = self._get_parameter_names(context)
        if loop_name in parameter_names:
            raise InvalidTemplateException(f"{key}: loop name '{loop_name}' conflicts with parameter name")

        # Validate template_body: must be a dictionary
        if not isinstance(template_body, dict):
            raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))

        # Resolve collection if it contains intrinsics
        resolved_collection = self._resolve_collection(collection, context)

        # Validate resolved collection: must be a list
        if not isinstance(resolved_collection, list):
            raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))

        # For list-of-lists format, resolve each item and validate
        if len(identifiers) > 1:
            resolved_items = []
            for item in resolved_collection:
                resolved_item = self._resolve_collection_item(item, context)
                if not isinstance(resolved_item, list) or len(resolved_item) != len(identifiers):
                    raise InvalidTemplateException(self._LAYOUT_ERROR_FMT.format(key))
                resolved_items.append(resolved_item)
            resolved_collection = resolved_items

        return identifiers, resolved_collection

    def _resolve_identifiers(self, identifier: Any, context: TemplateProcessingContext) -> List[str]:
        """
        Resolve and validate identifiers.

        Identifiers can be:
        - A string: "VariableName"
        - A list of strings: ["LogicalId", "TopicId"]
        - A list containing intrinsics: [{"Ref": "ParamName"}, "TopicId"]

        Args:
            identifier: The identifier value to resolve.
            context: The template processing context.

        Returns:
            A list of resolved identifier strings.
        """
        if isinstance(identifier, str):
            if not identifier:
                return []
            return [identifier]
        elif isinstance(identifier, list):
            resolved = []
            for item in identifier:
                if isinstance(item, str):
                    if not item:
                        return []
                    resolved.append(item)
                elif isinstance(item, dict):
                    # Try to resolve intrinsic
                    resolved_item = self._resolve_intrinsic(item, context)
                    if not isinstance(resolved_item, str) or not resolved_item:
                        return []
                    resolved.append(resolved_item)
                else:
                    return []
            return resolved
        else:
            return []

    def _resolve_intrinsic(self, value: Any, context: TemplateProcessingContext) -> Any:
        """
        Resolve an intrinsic function value.

        Args:
            value: The value to resolve.
            context: The template processing context.

        Returns:
            The resolved value, or the original value if no resolver is available.
        """
        if self._intrinsic_resolver is not None:
            return self._intrinsic_resolver.resolve_value(value)
        return value

    def _resolve_collection_item(self, item: Any, context: TemplateProcessingContext) -> Any:
        """
        Resolve a collection item that may contain intrinsics.

        For list-of-lists format, each item in the collection can be:
        - A list of values: [1, "1"]
        - An intrinsic that resolves to a list: {"Ref": "ValueList"}

        Args:
            item: The collection item to resolve.
            context: The template processing context.

        Returns:
            The resolved collection item.
        """
        if isinstance(item, list):
            return item

        if self._intrinsic_resolver is not None:
            resolved = self._intrinsic_resolver.resolve_value(item)
            # Handle CommaDelimitedList that was resolved to a string
            if isinstance(resolved, str) and "," in resolved:
                return [v.strip() for v in resolved.split(",")]
            return resolved

        return item

    def _check_identifier_conflicts(
        self, identifier: str, key: str, context: TemplateProcessingContext, parent_identifiers: List[str]
    ) -> None:
        """
        Check for identifier conflicts with parameter names and other loop identifiers.

        Args:
            identifier: The loop variable identifier to check.
            key: The ForEach key (for error messages).
            context: The template processing context.
            parent_identifiers: List of identifiers from parent ForEach loops.

        Raises:
            InvalidTemplateException: If the identifier conflicts with a parameter name
                                      or another loop identifier.
        """
        # Check for conflict with parameter names
        parameter_names = self._get_parameter_names(context)
        if identifier in parameter_names:
            raise InvalidTemplateException(f"{key}: identifier '{identifier}' conflicts with parameter name")

        # Check for conflict with parent loop identifiers
        if identifier in parent_identifiers:
            raise InvalidTemplateException(f"{key}: identifier '{identifier}' conflicts with another loop identifier")

    def _get_parameter_names(self, context: TemplateProcessingContext) -> set:
        """
        Get all parameter names from the template.

        Args:
            context: The template processing context.

        Returns:
            A set of parameter names.
        """
        parameter_names: set[str] = set()

        # Get parameters from the fragment
        if "Parameters" in context.fragment:
            parameters = context.fragment.get("Parameters", {})
            if isinstance(parameters, dict):
                parameter_names.update(parameters.keys())

        # Also check parsed_template if available
        if context.parsed_template is not None and context.parsed_template.parameters:
            parameter_names.update(context.parsed_template.parameters.keys())

        return parameter_names

    def _expand_foreach(
        self,
        key: str,
        value: List[Any],
        context: TemplateProcessingContext,
        parent_identifiers: Optional[List[str]] = None,
        identifiers: Optional[List[str]] = None,
        resolved_collection: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Expand a single Fn::ForEach construct into multiple outputs.

        Args:
            key: The ForEach key (e.g., "Fn::ForEach::Topics").
            value: The ForEach value (a 3-element list: [identifier, collection, body]).
            context: The template processing context.
            parent_identifiers: List of identifiers from parent ForEach loops.
            identifiers: Pre-resolved identifiers from _validate_and_resolve_foreach.
            resolved_collection: Pre-resolved collection from _validate_and_resolve_foreach.

        Returns:
            A dictionary containing all expanded entries.
        """
        if parent_identifiers is None:
            parent_identifiers = []
        if identifiers is None:
            identifiers = value[0] if isinstance(value[0], list) else [value[0]]
        if resolved_collection is None:
            resolved_collection = value[1]

        template_body = value[2]

        is_list_of_lists = len(identifiers) > 1
        LOG.debug("Expanding %s with %d collection items", key, len(resolved_collection))

        # Track current identifiers for nested loops
        current_identifiers = parent_identifiers + identifiers

        result: Dict[str, Any] = {}

        for item in resolved_collection:
            # Get values for each identifier
            if is_list_of_lists:
                # item is a list of values, one for each identifier
                item_values = [self._to_string(v) for v in item]
            else:
                # item is a single value
                item_values = [self._to_string(item)]

            # Substitute all identifiers in the template body
            expanded = template_body
            for ident, item_str in zip(identifiers, item_values):
                expanded = self._substitute_identifier(expanded, ident, item_str)

            # Recursively expand any nested ForEach constructs
            if isinstance(expanded, dict):
                expanded = self._process_section(expanded, context, current_identifiers)

            # Merge expanded entries into result
            self._merge_expanded(result, expanded, key)

        return result

    def _to_string(self, value: Any) -> str:
        """
        Convert a value to string for substitution.

        Handles special cases:
        - Booleans are converted to lowercase ("true"/"false") to match Kotlin behavior
        - Other types use standard str() conversion

        Args:
            value: The value to convert.

        Returns:
            The string representation of the value.
        """
        if isinstance(value, bool):
            # Use lowercase for booleans to match Kotlin/JSON behavior
            return "true" if value else "false"
        return str(value)

    def _substitute_identifier(self, template: Any, identifier: str, value: str) -> Any:
        """
        Substitute ${identifier} and {"Ref": "identifier"} with value throughout the template.

        This method recursively processes the template structure and replaces
        all occurrences of ${identifier} and {"Ref": "identifier"} with the
        provided value. The substitution is performed in:
        - String values (for ${identifier} syntax)
        - Dictionary keys (for ${identifier} syntax)
        - Dictionary values (for both syntaxes)
        - List items
        - Ref intrinsic functions referencing the identifier

        Args:
            template: The template structure to process (can be any type).
            identifier: The identifier to substitute (without ${} wrapper).
            value: The value to substitute in place of ${identifier}.

        Returns:
            The template with all ${identifier} and {"Ref": "identifier"} occurrences replaced.
        """
        if isinstance(template, str):
            # Replace ${identifier} with value in strings
            return template.replace(f"${{{identifier}}}", value)
        elif isinstance(template, dict):
            # Check if this is a Ref to the loop identifier
            if len(template) == 1 and "Ref" in template:
                ref_target = template["Ref"]
                if ref_target == identifier:
                    # Replace Ref to loop identifier with the value
                    return value

            # Process both keys and values in dictionaries
            return {
                self._substitute_identifier(k, identifier, value): self._substitute_identifier(v, identifier, value)
                for k, v in template.items()
            }
        elif isinstance(template, list):
            # Process each item in lists
            return [self._substitute_identifier(item, identifier, value) for item in template]
        else:
            # Return primitives (int, float, bool, None) unchanged
            return template

    def _resolve_collection(self, collection: Any, context: TemplateProcessingContext) -> Any:
        """
        Resolve a collection that may contain intrinsic functions.

        If the collection is an intrinsic function (e.g., Ref to a parameter),
        it is resolved using the intrinsic resolver. If no resolver is available
        or the collection is already a list, it is returned as-is.

        Cloud-dependent intrinsics (Fn::GetAtt, Fn::ImportValue) and dynamic
        references (SSM/Secrets Manager) are not supported and will raise
        an error with a helpful workaround message.

        Args:
            collection: The collection value to resolve.
            context: The template processing context.

        Returns:
            The resolved collection value.

        Raises:
            InvalidTemplateException: If the collection contains cloud-dependent
                                      intrinsics that cannot be resolved locally.
        """
        # If collection is already a list, check for cloud-dependent values in items
        if isinstance(collection, list):
            self._validate_collection_items(collection)
            return collection

        # Check for cloud-dependent intrinsics before attempting resolution
        self._validate_collection_resolvability(collection)

        # If we have an intrinsic resolver, try to resolve the collection
        if self._intrinsic_resolver is not None:
            resolved = self._intrinsic_resolver.resolve_value(collection)
            # Handle CommaDelimitedList that was resolved to a string
            if isinstance(resolved, str) and "," in resolved:
                return [item.strip() for item in resolved.split(",")]
            return resolved

        # Return collection as-is if we can't resolve it
        return collection

    def _validate_collection_resolvability(self, collection: Any) -> None:
        """
        Validate that a collection can be resolved locally.

        Cloud-dependent intrinsics (Fn::GetAtt, Fn::ImportValue) and dynamic
        references (SSM/Secrets Manager) cannot be resolved locally and will
        raise an error with a helpful workaround message.

        Args:
            collection: The collection value to validate.

        Raises:
            InvalidTemplateException: If the collection contains cloud-dependent
                                      intrinsics that cannot be resolved locally.
        """
        if isinstance(collection, dict) and len(collection) == 1:
            key = next(iter(collection.keys()))

            # Check for cloud-dependent intrinsics
            _CLOUD_DEPENDENT = ("Fn::GetAtt", "!GetAtt", "Fn::ImportValue", "!ImportValue")
            if key in _CLOUD_DEPENDENT:
                target_str = str(collection[key])
                reason = (
                    f"The collection uses '{key}' which requires" " deployed resources and cannot be resolved locally."
                )
                raise InvalidTemplateException(
                    self._build_unresolvable_collection_error(reason, f"Target: {target_str}")
                )

        # Check for SSM/Secrets Manager dynamic references
        if isinstance(collection, str):
            self._check_dynamic_reference(collection)

    def _validate_collection_items(self, collection: list) -> None:
        """
        Validate that collection items do not contain cloud-dependent values.

        Args:
            collection: The collection list to validate.

        Raises:
            InvalidTemplateException: If any item contains cloud-dependent values.
        """
        for item in collection:
            if isinstance(item, dict):
                self._validate_collection_resolvability(item)
            elif isinstance(item, str):
                self._check_dynamic_reference(item)
            elif isinstance(item, list):
                self._validate_collection_items(item)

    def _check_dynamic_reference(self, value: str) -> None:
        """
        Check if a string value contains SSM/Secrets Manager dynamic references.

        Dynamic references have the format {{resolve:service:reference}}
        where service can be ssm, ssm-secure, or secretsmanager.

        Args:
            value: The string value to check.

        Raises:
            InvalidTemplateException: If the value contains a dynamic reference.
        """
        match = _DYNAMIC_REF_PATTERN.search(value)

        if match:
            service = match.group(1)
            service_name = {
                "ssm": "AWS Systems Manager Parameter Store",
                "ssm-secure": "AWS Systems Manager Parameter Store (SecureString)",
                "secretsmanager": "AWS Secrets Manager",
            }.get(service.lower(), service)
            raise InvalidTemplateException(
                self._build_unresolvable_collection_error(
                    f"The collection uses a dynamic reference to {service_name} which requires AWS API calls "
                    f"and cannot be resolved locally.",
                    f"Value: {value}",
                )
            )

    _COLLECTION_WORKAROUND = (
        "Workaround: Use a parameter instead:\n"
        "  Parameters:\n"
        "    CollectionValues:\n"
        "      Type: CommaDelimitedList\n\n"
        "  Fn::ForEach::MyLoop:\n"
        "    - Item\n"
        "    - !Ref CollectionValues\n"
        "    - ...\n\n"
        'Then provide the value: sam build --parameter-overrides CollectionValues="Value1,Value2,Value3"'
    )

    def _build_unresolvable_collection_error(self, reason: str, detail: str) -> str:
        """
        Build an error message for unresolvable Fn::ForEach collections.

        Args:
            reason: Why the collection cannot be resolved locally.
            detail: The specific value or target that caused the error.

        Returns:
            A formatted error message with workaround suggestion.
        """
        return (
            f"Unable to resolve Fn::ForEach collection locally. "
            f"{reason}\n\n"
            f"{detail}\n\n"
            f"{self._COLLECTION_WORKAROUND}"
        )

    def get_foreach_loop_name(self, key: str) -> str:
        """
        Extract the loop name from a Fn::ForEach key.

        For a key like "Fn::ForEach::Topics", this returns "Topics".

        Args:
            key: The ForEach key.

        Returns:
            The loop name portion of the key.
        """
        if not is_foreach_key(key):
            raise ValueError(f"Key '{key}' is not a valid Fn::ForEach key")
        return key[len(FOREACH_PREFIX) :]
