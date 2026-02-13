"""
Fn::FindInMap intrinsic function resolver.

This module provides the resolver for the CloudFormation Fn::FindInMap intrinsic
function, which looks up values in the Mappings section of a template.

The resolver supports the AWS::LanguageExtensions enhancement that allows
specifying a DefaultValue to return when the map lookup fails.

Requirements:
    - 5.1: WHEN Fn::FindInMap is applied with valid map name, top-level key, and
           second-level key, THEN THE Resolver SHALL return the corresponding
           value from the Mappings section
    - 5.2: WHEN Fn::FindInMap includes a DefaultValue option and the top-level key
           is not found, THEN THE Resolver SHALL return the default value
    - 5.3: WHEN Fn::FindInMap includes a DefaultValue option and the second-level key
           is not found, THEN THE Resolver SHALL return the default value
    - 5.4: WHEN Fn::FindInMap keys contain nested intrinsic functions (Fn::Select,
           Fn::Split, Fn::If, Fn::Join, Fn::Sub), THEN THE Resolver SHALL resolve
           those intrinsics before performing the lookup
    - 5.5: WHEN Fn::FindInMap is applied with an invalid layout, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
    - 5.6: WHEN Fn::FindInMap lookup fails without a DefaultValue, THEN THE Resolver
           SHALL raise an Invalid_Template_Exception
"""

from typing import Any, Dict

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.resolvers.base import IntrinsicFunctionResolver


class FnFindInMapResolver(IntrinsicFunctionResolver):
    """
    Resolves Fn::FindInMap intrinsic function with optional DefaultValue support.

    Fn::FindInMap returns the value corresponding to keys in a two-level map
    declared in the Mappings section of a template.

    Standard format:
        {"Fn::FindInMap": [MapName, TopLevelKey, SecondLevelKey]}

    With DefaultValue (AWS::LanguageExtensions):
        {"Fn::FindInMap": [MapName, TopLevelKey, SecondLevelKey, {"DefaultValue": value}]}

    The resolver:
    - Resolves any nested intrinsic functions in the keys before lookup
    - Performs the map lookup with resolved keys
    - Returns the DefaultValue if provided and lookup fails
    - Raises InvalidTemplateException if lookup fails without DefaultValue

    Attributes:
        FUNCTION_NAMES: List containing "Fn::FindInMap"

    Example:
        >>> # Given Mappings: {"RegionMap": {"us-east-1": {"AMI": "ami-12345"}}}
        >>> resolver = FnFindInMapResolver(context, parent_resolver)
        >>> resolver.resolve({"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]})
        "ami-12345"

        >>> # With DefaultValue when key not found
        >>> resolver.resolve({
        ...     "Fn::FindInMap": ["RegionMap", "invalid-region", "AMI",
        ...                       {"DefaultValue": "ami-default"}]
        ... })
        "ami-default"

    Raises:
        InvalidTemplateException: If the layout is incorrect or lookup fails
                                  without a DefaultValue.

    Requirements:
        - 5.1: Return the corresponding value from the Mappings section
        - 5.2: Return DefaultValue when top-level key is not found
        - 5.3: Return DefaultValue when second-level key is not found
        - 5.4: Resolve nested intrinsics in keys before lookup
        - 5.5: Raise InvalidTemplateException for invalid layout
        - 5.6: Raise InvalidTemplateException when lookup fails without DefaultValue
    """

    FUNCTION_NAMES = ["Fn::FindInMap"]

    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the Fn::FindInMap intrinsic function.

        This method extracts the arguments from the Fn::FindInMap function,
        resolves any nested intrinsic functions in the keys, performs the
        map lookup, and returns the result or DefaultValue.

        Args:
            value: A dictionary representing the Fn::FindInMap intrinsic function.
                   E.g., {"Fn::FindInMap": ["MapName", "TopKey", "SecondKey"]} or
                   {"Fn::FindInMap": ["MapName", "TopKey", "SecondKey",
                                      {"DefaultValue": "fallback"}]}

        Returns:
            The value from the Mappings section, or the DefaultValue if provided
            and the lookup fails.

        Raises:
            InvalidTemplateException: If the layout is incorrect (not a list,
                                      fewer than 3 elements) or if the lookup
                                      fails without a DefaultValue.

        Example:
            >>> resolver.resolve({"Fn::FindInMap": ["RegionMap", "us-east-1", "AMI"]})
            "ami-12345"
            >>> resolver.resolve({"Fn::FindInMap": ["RegionMap", "invalid", "AMI",
            ...                                     {"DefaultValue": "default"}]})
            "default"
        """
        # Extract the arguments from the intrinsic function
        args = self.get_function_args(value)

        # Validate basic layout - must be a list with at least 3 elements
        if not isinstance(args, list) or len(args) < 3:
            raise InvalidTemplateException("Fn::FindInMap layout is incorrect")

        # Extract the map name, top-level key, and second-level key
        map_name_arg = args[0]
        top_key_arg = args[1]
        second_key_arg = args[2]

        # Resolve any nested intrinsic functions in the keys
        # This handles cases like {"Fn::FindInMap": [{"Ref": "MapParam"}, ...]}
        if self.parent is not None:
            map_name = self.parent.resolve_value(map_name_arg)
            top_key = self.parent.resolve_value(top_key_arg)
            second_key = self.parent.resolve_value(second_key_arg)
        else:
            # If no parent resolver, use args as-is (for testing)
            map_name = map_name_arg
            top_key = top_key_arg
            second_key = second_key_arg

        # Validate resolved keys are strings
        if not isinstance(map_name, str):
            raise InvalidTemplateException("Fn::FindInMap layout is incorrect")
        if not isinstance(top_key, str):
            raise InvalidTemplateException("Fn::FindInMap layout is incorrect")
        if not isinstance(second_key, str):
            raise InvalidTemplateException("Fn::FindInMap layout is incorrect")

        # Check for DefaultValue option (4th argument)
        default_value: Any = None
        has_default = False
        if len(args) >= 4:
            options = args[3]
            if isinstance(options, dict) and "DefaultValue" in options:
                has_default = True
                default_value = options["DefaultValue"]
            elif options is not None and not isinstance(options, dict):
                # If 4th argument exists and is not a dict, it's invalid
                raise InvalidTemplateException("Fn::FindInMap layout is incorrect")
            # If 4th argument is a dict without DefaultValue, treat as no default

        # Get the Mappings section from the parsed template
        mappings = self._get_mappings()

        # Perform the lookup
        try:
            # Check if map exists
            if map_name not in mappings:
                if has_default:
                    return self._resolve_default_value(default_value)
                raise InvalidTemplateException(f"Fn::FindInMap cannot find map '{map_name}' in Mappings")

            map_data = mappings[map_name]

            # Check if top-level key exists
            if not isinstance(map_data, dict) or top_key not in map_data:
                if has_default:
                    return self._resolve_default_value(default_value)
                raise InvalidTemplateException(f"Fn::FindInMap cannot find key '{top_key}' in map '{map_name}'")

            top_level_data = map_data[top_key]

            # Check if second-level key exists
            if not isinstance(top_level_data, dict) or second_key not in top_level_data:
                if has_default:
                    return self._resolve_default_value(default_value)
                raise InvalidTemplateException(
                    f"Fn::FindInMap cannot find key '{second_key}' in " f"map '{map_name}' under key '{top_key}'"
                )

            # Get the found value
            result = top_level_data[second_key]

            # Treat null values as "not found" - Kotlin behavior
            if result is None:
                if has_default:
                    return self._resolve_default_value(default_value)
                # Get resource type from context for error message
                resource_type = self._get_current_resource_type()
                raise InvalidTemplateException(
                    f"Mappings not found in template for key /{top_key}/{second_key} on resourceType {resource_type}"
                )

            return result

        except InvalidTemplateException:
            # Re-raise InvalidTemplateException as-is
            raise
        except Exception as e:
            # Wrap any other exceptions
            if has_default:
                return self._resolve_default_value(default_value)
            raise InvalidTemplateException(f"Fn::FindInMap lookup failed: {e}") from e

    def _get_mappings(self) -> Dict[str, Any]:
        """
        Get the Mappings section from the template context.

        Returns:
            The Mappings dictionary from the parsed template, or an empty
            dictionary if no parsed template or mappings are available.
        """
        if self.context.parsed_template is not None:
            return dict(self.context.parsed_template.mappings or {})

        # Fallback to fragment if parsed_template not available
        mappings = self.context.fragment.get("Mappings", {})
        return dict(mappings) if isinstance(mappings, dict) else {}

    def _resolve_default_value(self, default_value: Any) -> Any:
        """
        Resolve the default value, handling any nested intrinsic functions.

        Args:
            default_value: The default value to resolve.

        Returns:
            The resolved default value.
        """
        if self.parent is not None:
            return self.parent.resolve_value(default_value)
        return default_value

    def _get_current_resource_type(self) -> str:
        """
        Get the resource type from the current context.

        This is used for error messages to match Kotlin behavior.

        Returns:
            The resource type string, or "Unknown" if not available.
        """
        # Try to get from fragment's Resources section
        fragment = self.context.fragment
        if "Resources" in fragment and isinstance(fragment["Resources"], dict):
            # Return the first resource type found (best effort)
            for resource in fragment["Resources"].values():
                if isinstance(resource, dict) and "Type" in resource:
                    return str(resource["Type"])
        return "Unknown"
