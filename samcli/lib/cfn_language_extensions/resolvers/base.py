"""
Base class and infrastructure for CloudFormation intrinsic function resolvers.

This module provides the foundational classes and constants for resolving
CloudFormation intrinsic functions during template processing.

The resolver pattern uses:
- IntrinsicFunctionResolver: Base class for individual function resolvers
- Resolver chain: Composable pattern for handling multiple intrinsic functions
- Constants: Define which functions can be resolved locally vs. preserved
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from samcli.lib.cfn_language_extensions.models import TemplateProcessingContext


# Intrinsic functions that can be resolved locally during template processing.
# These functions can be evaluated without access to deployed CloudFormation resources.
RESOLVABLE_INTRINSICS = {
    "Fn::Length",  # Returns count of list elements
    "Fn::ToJsonString",  # Converts value to JSON string
    "Fn::FindInMap",  # Looks up values in Mappings section
    "Fn::If",  # Conditional value selection
    "Fn::Sub",  # String substitution with variables
    "Fn::Join",  # Concatenates strings with delimiter
    "Fn::Split",  # Splits string into list
    "Fn::Select",  # Selects item from list by index
    "Fn::Base64",  # Base64 encodes a string
    "Fn::Equals",  # Compares two values for equality
    "Fn::And",  # Logical AND of conditions
    "Fn::Or",  # Logical OR of conditions
    "Fn::Not",  # Logical NOT of condition
    "Ref",  # Only for parameters and pseudo-parameters
}

# Intrinsic functions that must be preserved for CloudFormation to resolve.
# These functions require access to deployed resources or runtime information.
UNRESOLVABLE_INTRINSICS = {
    "Fn::GetAtt",  # Gets attribute from a resource (requires deployed resource)
    "Fn::ImportValue",  # Imports value from another stack's exports
    "Fn::GetAZs",  # Gets availability zones (runtime information)
    "Fn::Cidr",  # Generates CIDR blocks (complex calculation)
    "Ref",  # When referencing resources (not parameters)
}


class IntrinsicFunctionResolver(ABC):
    """
    Base class for resolving CloudFormation intrinsic functions.

    This abstract base class defines the interface for intrinsic function
    resolvers. Each resolver handles one or more specific intrinsic functions
    (e.g., Fn::Length, Fn::Sub) and knows how to evaluate them.

    The resolver pattern supports:
    - Pattern matching via `can_resolve()` to determine if a value is handled
    - Resolution via `resolve()` to evaluate the intrinsic function
    - Composition via parent resolver for nested intrinsic resolution

    Subclasses must:
    - Set FUNCTION_NAMES class attribute with the intrinsic function names handled
    - Implement the `resolve()` method to evaluate the function

    Attributes:
        FUNCTION_NAMES: List of intrinsic function names this resolver handles.
                        E.g., ["Fn::Length"] or ["Fn::Join", "Fn::Split"]
        context: The template processing context with parameters, mappings, etc.
        parent: The parent IntrinsicResolver for resolving nested intrinsics.
    """

    # Intrinsic function names this resolver handles.
    # Subclasses must override this with their specific function names.
    FUNCTION_NAMES: List[str] = []

    def __init__(
        self, context: "TemplateProcessingContext", parent_resolver: Optional["IntrinsicResolver"] = None
    ) -> None:
        """
        Initialize the resolver with context and parent resolver.

        Args:
            context: The template processing context containing parameters,
                     mappings, conditions, and other template state.
            parent_resolver: The parent IntrinsicResolver used for resolving
                             nested intrinsic functions. Can be None for
                             testing or standalone use.
        """
        self.context = context
        self.parent = parent_resolver

    def can_resolve(self, value: Any) -> bool:
        """
        Check if this resolver can handle the given value.

        This method implements pattern matching for CloudFormation intrinsic
        functions. An intrinsic function is represented as a dictionary with
        exactly one key that matches one of the function names this resolver
        handles.

        Args:
            value: The value to check. Can be any type.

        Returns:
            True if this resolver can handle the value (i.e., it's a dict
            with exactly one key matching a function name in FUNCTION_NAMES).
            False otherwise.
        """
        # Must be a dictionary
        if not isinstance(value, dict):
            return False

        # Must have exactly one key (intrinsic function pattern)
        if len(value) != 1:
            return False

        # The key must be one of the function names this resolver handles
        key = next(iter(value.keys()))
        return key in self.FUNCTION_NAMES

    @abstractmethod
    def resolve(self, value: Dict[str, Any]) -> Any:
        """
        Resolve the intrinsic function and return the result.

        This method must be implemented by subclasses to evaluate the
        specific intrinsic function. The value is guaranteed to be a
        dictionary with exactly one key matching one of FUNCTION_NAMES
        (as verified by can_resolve()).

        Implementations should:
        - Extract the function arguments from the value
        - Resolve any nested intrinsic functions using self.parent.resolve_value()
        - Perform the function-specific logic
        - Return the resolved value
        - Raise InvalidTemplateException for invalid inputs

        Args:
            value: A dictionary representing the intrinsic function.
                   E.g., {"Fn::Length": [1, 2, 3]}

        Returns:
            The resolved value. The type depends on the specific function.

        Raises:
            InvalidTemplateException: If the function arguments are invalid
                                      or resolution fails.
        """
        raise NotImplementedError(f"Subclass must implement resolve() for {self.FUNCTION_NAMES}")

    def get_function_name(self, value: Dict[str, Any]) -> str:
        """
        Extract the function name from an intrinsic function value.

        This is a utility method for subclasses that handle multiple
        function names and need to determine which specific function
        is being resolved.

        Args:
            value: A dictionary representing the intrinsic function.

        Returns:
            The function name (the single key in the dictionary).
        """
        return next(iter(value.keys()))

    def get_function_args(self, value: Dict[str, Any]) -> Any:
        """
        Extract the function arguments from an intrinsic function value.

        This is a utility method for subclasses to easily access the
        arguments of the intrinsic function.

        Args:
            value: A dictionary representing the intrinsic function.

        Returns:
            The function arguments (the single value in the dictionary).
        """
        return next(iter(value.values()))


class IntrinsicResolver:
    """
    Orchestrator for resolving intrinsic functions in CloudFormation templates.

    This class manages a chain of IntrinsicFunctionResolver instances and
    coordinates the resolution of intrinsic functions throughout a template.
    It provides the `resolve_value()` method that recursively walks through
    template structures and resolves intrinsic functions.

    The resolver chain pattern allows:
    - Composing multiple resolvers for different intrinsic functions
    - Recursive resolution of nested intrinsic functions
    - Partial resolution mode (preserving unresolvable references)

    Partial Resolution Mode:
        When context.resolution_mode is ResolutionMode.PARTIAL, the resolver
        preserves intrinsic functions that cannot be resolved locally:
        - Fn::GetAtt: Requires deployed resource attributes
        - Fn::ImportValue: Requires cross-stack exports
        - Ref to resources: Requires deployed resource physical IDs

        Language extension functions are still resolved in partial mode:
        - Fn::ForEach, Fn::Length, Fn::ToJsonString, Fn::FindInMap with DefaultValue
        - Fn::If conditions where the condition value is known

    Attributes:
        context: The template processing context.
        resolvers: List of IntrinsicFunctionResolver instances in the chain.
        preserve_functions: Set of function names to preserve in partial mode.
    """

    # Default functions to preserve in partial resolution mode.
    # These functions require deployed resources or cross-stack information.
    DEFAULT_PRESERVE_FUNCTIONS = {
        "Fn::GetAtt",  # Requires deployed resource attributes
        "Fn::ImportValue",  # Requires cross-stack exports
        "Fn::GetAZs",  # Requires runtime AWS information
        "Fn::Cidr",  # Complex calculation, often preserved
    }

    def __init__(self, context: "TemplateProcessingContext", preserve_functions: Optional[set] = None) -> None:
        """
        Initialize the orchestrator with a template processing context.

        Args:
            context: The template processing context containing parameters,
                     mappings, conditions, and other template state.
            preserve_functions: Optional set of function names to preserve
                                in partial resolution mode. If None, uses
                                DEFAULT_PRESERVE_FUNCTIONS. This allows
                                configuration of which functions to preserve.
        """
        self.context = context
        self._resolvers: List[IntrinsicFunctionResolver] = []
        self._preserve_functions = (
            preserve_functions if preserve_functions is not None else self.DEFAULT_PRESERVE_FUNCTIONS.copy()
        )

    @property
    def preserve_functions(self) -> set:
        """
        Get the set of function names to preserve in partial mode.

        Returns:
            A copy of the preserve functions set.
        """
        return self._preserve_functions.copy()

    def set_preserve_functions(self, functions: set) -> "IntrinsicResolver":
        """
        Set the functions to preserve in partial resolution mode.

        This method allows runtime configuration of which intrinsic
        functions should be preserved rather than resolved.

        Args:
            functions: Set of function names to preserve.

        Returns:
            Self for method chaining.
        """
        self._preserve_functions = functions.copy()
        return self

    def add_preserve_function(self, function_name: str) -> "IntrinsicResolver":
        """
        Add a function to the preserve list.

        Args:
            function_name: The intrinsic function name to preserve.

        Returns:
            Self for method chaining.
        """
        self._preserve_functions.add(function_name)
        return self

    def remove_preserve_function(self, function_name: str) -> "IntrinsicResolver":
        """
        Remove a function from the preserve list.

        Args:
            function_name: The intrinsic function name to remove.

        Returns:
            Self for method chaining.
        """
        self._preserve_functions.discard(function_name)
        return self

    def register_resolver(
        self,
        resolver_class: type,
    ) -> "IntrinsicResolver":
        """
        Register a resolver class with this orchestrator.

        Creates an instance of the resolver class and adds it to the
        resolver chain. Returns self for method chaining.

        Args:
            resolver_class: A subclass of IntrinsicFunctionResolver.

        Returns:
            Self for method chaining.
        """
        resolver = resolver_class(self.context, self)
        self._resolvers.append(resolver)
        return self

    def add_resolver(self, resolver: IntrinsicFunctionResolver) -> "IntrinsicResolver":
        """
        Add an already-instantiated resolver to the chain.

        This method allows adding pre-configured resolver instances
        rather than having the orchestrator create them.

        Args:
            resolver: An IntrinsicFunctionResolver instance.

        Returns:
            Self for method chaining.
        """
        self._resolvers.append(resolver)
        return self

    def _is_intrinsic_function(self, value: Any) -> bool:
        """
        Check if a value represents an intrinsic function.

        An intrinsic function is a dict with exactly one key that starts
        with "Fn::" or is "Ref" or "Condition".

        Args:
            value: The value to check.

        Returns:
            True if the value is an intrinsic function pattern.
        """
        if not isinstance(value, dict) or len(value) != 1:
            return False
        key = next(iter(value.keys()))
        return key.startswith("Fn::") or key in ("Ref", "Condition")

    def _get_intrinsic_name(self, value: Dict[str, Any]) -> str:
        """
        Get the intrinsic function name from a value.

        Args:
            value: A dict representing an intrinsic function.

        Returns:
            The function name (the single key).
        """
        return next(iter(value.keys()))

    def _should_preserve(self, value: Dict[str, Any]) -> bool:
        """
        Determine if an intrinsic function should be preserved.

        In partial resolution mode, certain intrinsic functions are
        preserved rather than resolved because they require information
        that is only available at deployment time.

        Args:
            value: A dict representing an intrinsic function.

        Returns:
            True if the function should be preserved, False otherwise.
        """
        # Import here to avoid circular imports
        from samcli.lib.cfn_language_extensions.models import ResolutionMode

        # Only preserve in partial resolution mode
        if self.context.resolution_mode != ResolutionMode.PARTIAL:
            return False

        fn_name = self._get_intrinsic_name(value)

        # Check if this function is in the preserve list
        if fn_name in self._preserve_functions:
            return True

        # Special handling for Ref - only preserve references to resources
        if fn_name == "Ref":
            return self._is_resource_ref(value)

        return False

    def _is_resource_ref(self, value: Dict[str, Any]) -> bool:
        """
        Check if a Ref intrinsic references a resource (vs parameter/pseudo-param).

        Refs to parameters and pseudo-parameters can be resolved locally,
        but Refs to resources must be preserved for CloudFormation.

        Args:
            value: A dict representing a Ref intrinsic function.

        Returns:
            True if the Ref is to a resource, False if to a parameter
            or pseudo-parameter.
        """
        ref_target = value.get("Ref")
        if not isinstance(ref_target, str):
            return False

        # Check if it's a pseudo-parameter
        pseudo_params = {
            "AWS::AccountId",
            "AWS::NotificationARNs",
            "AWS::NoValue",
            "AWS::Partition",
            "AWS::Region",
            "AWS::StackId",
            "AWS::StackName",
            "AWS::URLSuffix",
        }
        if ref_target in pseudo_params:
            return False

        # Check if it's a template parameter
        if self.context.parsed_template is not None:
            if ref_target in self.context.parsed_template.parameters:
                return False

        # Check parameter_values as fallback
        if ref_target in self.context.parameter_values:
            return False

        # If not a pseudo-param or template param, assume it's a resource ref
        return True

    def resolve_value(self, value: Any) -> Any:
        """
        Resolve intrinsic functions in a value recursively.

        This method walks through the value structure (dicts, lists, primitives)
        and resolves any intrinsic functions found. Nested intrinsic functions
        are resolved recursively.

        In partial resolution mode (context.resolution_mode == ResolutionMode.PARTIAL),
        unresolvable intrinsic functions are preserved in the output:
        - Fn::GetAtt: Preserved (requires deployed resource attributes)
        - Fn::ImportValue: Preserved (requires cross-stack exports)
        - Ref to resources: Preserved (requires deployed resource physical IDs)

        Language extension functions are always resolved:
        - Fn::ForEach, Fn::Length, Fn::ToJsonString, Fn::FindInMap with DefaultValue

        Args:
            value: The value to resolve. Can be any type.

        Returns:
            The resolved value with intrinsic functions evaluated,
            or preserved intrinsic functions in partial mode.
        """
        # Check if this is an intrinsic function that should be preserved
        if self._is_intrinsic_function(value) and self._should_preserve(value):
            # Still recursively resolve the arguments in case they contain
            # resolvable intrinsics
            fn_name = self._get_intrinsic_name(value)
            fn_args = value[fn_name]
            resolved_args = self.resolve_value(fn_args)
            return {fn_name: resolved_args}

        # Check if any resolver can handle this value
        for resolver in self._resolvers:
            if resolver.can_resolve(value):
                return resolver.resolve(value)

        # Recursively process dicts and lists
        if isinstance(value, dict):
            return {k: self.resolve_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve_value(item) for item in value]

        # Return primitives as-is
        return value

    @property
    def resolvers(self) -> List[IntrinsicFunctionResolver]:
        """
        Get the list of registered resolvers.

        Returns:
            A copy of the resolver list.
        """
        return list(self._resolvers)
