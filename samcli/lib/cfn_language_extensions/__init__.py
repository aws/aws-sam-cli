"""
CloudFormation Language Extensions Python Package.

This package provides a standalone library for processing CloudFormation templates
with extended intrinsic functions (Fn::ForEach, Fn::Length, Fn::ToJsonString,
Fn::FindInMap with DefaultValue).

The package enables local template validation, CI/CD pipeline integration,
IDE tooling, and testing without deployment. It is designed to integrate
with the AWS SAM ecosystem.

Internal Package: CFNLanguageExtensions
Commit: ab10aed4c2a72e0307e7f209141a22cdd2e27562
"""

import importlib

__version__ = "0.1.0"

# Mapping from public symbol name to the submodule that defines it.
# Imports are deferred until first access via __getattr__.
_LAZY_IMPORTS = {
    # API
    "create_default_intrinsic_resolver": "samcli.lib.cfn_language_extensions.api",
    "create_default_pipeline": "samcli.lib.cfn_language_extensions.api",
    "load_template": "samcli.lib.cfn_language_extensions.api",
    "load_template_from_json": "samcli.lib.cfn_language_extensions.api",
    "load_template_from_yaml": "samcli.lib.cfn_language_extensions.api",
    "process_template": "samcli.lib.cfn_language_extensions.api",
    # Exceptions
    "InvalidTemplateException": "samcli.lib.cfn_language_extensions.exceptions",
    "PublicFacingErrorMessages": "samcli.lib.cfn_language_extensions.exceptions",
    "UnresolvableReferenceError": "samcli.lib.cfn_language_extensions.exceptions",
    # Models
    "PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES": "samcli.lib.cfn_language_extensions.models",
    "DynamicArtifactProperty": "samcli.lib.cfn_language_extensions.models",
    "ParsedTemplate": "samcli.lib.cfn_language_extensions.models",
    "PseudoParameterValues": "samcli.lib.cfn_language_extensions.models",
    "ResolutionMode": "samcli.lib.cfn_language_extensions.models",
    "TemplateProcessingContext": "samcli.lib.cfn_language_extensions.models",
    # Pipeline
    "ProcessingPipeline": "samcli.lib.cfn_language_extensions.pipeline",
    "TemplateProcessor": "samcli.lib.cfn_language_extensions.pipeline",
    # Processors
    "TemplateParsingProcessor": "samcli.lib.cfn_language_extensions.processors",
    # Resolvers
    "IntrinsicFunctionResolver": "samcli.lib.cfn_language_extensions.resolvers",
    "RESOLVABLE_INTRINSICS": "samcli.lib.cfn_language_extensions.resolvers",
    "UNRESOLVABLE_INTRINSICS": "samcli.lib.cfn_language_extensions.resolvers",
    "IntrinsicResolver": "samcli.lib.cfn_language_extensions.resolvers.base",
    # Serialization
    "serialize_to_json": "samcli.lib.cfn_language_extensions.serialization",
    "serialize_to_yaml": "samcli.lib.cfn_language_extensions.serialization",
    # SAM Integration
    "AWS_LANGUAGE_EXTENSIONS_TRANSFORM": "samcli.lib.cfn_language_extensions.sam_integration",
    "LanguageExtensionResult": "samcli.lib.cfn_language_extensions.sam_integration",
    "check_using_language_extension": "samcli.lib.cfn_language_extensions.sam_integration",
    "contains_loop_variable": "samcli.lib.cfn_language_extensions.sam_integration",
    "detect_dynamic_artifact_properties": "samcli.lib.cfn_language_extensions.sam_integration",
    "detect_foreach_dynamic_properties": "samcli.lib.cfn_language_extensions.sam_integration",
    "expand_language_extensions": "samcli.lib.cfn_language_extensions.sam_integration",
    "process_template_for_sam_cli": "samcli.lib.cfn_language_extensions.sam_integration",
    "resolve_collection": "samcli.lib.cfn_language_extensions.sam_integration",
    "resolve_parameter_collection": "samcli.lib.cfn_language_extensions.sam_integration",
    "substitute_loop_variable": "samcli.lib.cfn_language_extensions.sam_integration",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value  # cache so subsequent access skips __getattr__
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    # Exceptions
    "InvalidTemplateException",
    "UnresolvableReferenceError",
    "PublicFacingErrorMessages",
    # Models
    "ResolutionMode",
    "PseudoParameterValues",
    "ParsedTemplate",
    "TemplateProcessingContext",
    "DynamicArtifactProperty",
    "PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES",
    # Pipeline
    "TemplateProcessor",
    "ProcessingPipeline",
    # Processors
    "TemplateParsingProcessor",
    # Resolvers
    "IntrinsicFunctionResolver",
    "IntrinsicResolver",
    "RESOLVABLE_INTRINSICS",
    "UNRESOLVABLE_INTRINSICS",
    # Serialization
    "serialize_to_json",
    "serialize_to_yaml",
    # API
    "process_template",
    "create_default_pipeline",
    "create_default_intrinsic_resolver",
    "load_template_from_json",
    "load_template_from_yaml",
    "load_template",
    # SAM Integration
    "LanguageExtensionResult",
    "check_using_language_extension",
    "expand_language_extensions",
    "process_template_for_sam_cli",
    "AWS_LANGUAGE_EXTENSIONS_TRANSFORM",
    "substitute_loop_variable",
]
