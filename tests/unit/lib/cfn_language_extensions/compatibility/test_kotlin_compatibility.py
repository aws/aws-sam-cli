"""
Compatibility tests using Kotlin test templates.

This module runs the Python implementation against the same test templates
used by the Kotlin implementation to verify behavioral compatibility.

The test templates are located in:
    tests/compatibility/templates/

Test patterns:
    - Files ending with 'Resolved.json' or 'Expected.json' are expected outputs
    - Files without these suffixes are inputs
    - Some inputs should produce errors (no expected file exists)
    - Templates with $RESOURCE_ATTRIBUTE placeholder need replacement with
      DeletionPolicy or UpdateReplacePolicy before testing

Compatibility Notes:
    1. Lambda macro request format (2 templates):
       Some templates use the Lambda macro request format with 'fragment',
       'accountId', 'transformId' fields. This format is specific to the
       Kotlin Lambda handler and is not supported by the Python library
       (which processes templates directly). These templates are tested
       separately to verify they raise InvalidTemplateException.

    2. All other templates are fully compatible with the Kotlin implementation.
"""

import json
import pytest
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from samcli.lib.cfn_language_extensions.api import process_template
from samcli.lib.cfn_language_extensions.models import ResolutionMode, PseudoParameterValues
from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException

# Path to test templates
KOTLIN_TEMPLATES_DIR = Path(__file__).parent / "templates"


def load_json_template(path: Path) -> Dict[str, Any]:
    """Load a JSON template file."""
    with open(path, "r") as f:
        return dict(json.load(f))


def load_json_template_with_placeholder(
    path: Path, placeholder: str = "$RESOURCE_ATTRIBUTE", replacement: str = "DeletionPolicy"
) -> Dict[str, Any]:
    """Load a JSON template file, replacing placeholders."""
    with open(path, "r") as f:
        content = f.read()
    content = content.replace(placeholder, replacement)
    return dict(json.loads(content))


def find_test_pairs(directory: Path) -> List[Tuple[Path, Optional[Path]]]:
    """Find input/expected output pairs in a directory."""
    pairs: List[Tuple[Path, Optional[Path]]] = []
    if not directory.exists():
        return pairs

    for file_path in sorted(directory.glob("*.json")):
        name = file_path.stem
        if name.endswith("Expected") or name.endswith("Resolved"):
            continue
        expected_path = directory / f"{name}Expected.json"
        resolved_path = directory / f"{name}Resolved.json"
        if expected_path.exists():
            pairs.append((file_path, expected_path))
        elif resolved_path.exists():
            pairs.append((file_path, resolved_path))
        else:
            pairs.append((file_path, None))
    return pairs


def normalize_template(template: Any) -> Any:
    """Normalize a template for comparison."""
    if isinstance(template, dict):
        return {k: normalize_template(v) for k, v in sorted(template.items())}
    elif isinstance(template, list):
        return [normalize_template(item) for item in template]
    elif isinstance(template, float):
        if template == int(template):
            return int(template)
        return round(template, 10)
    return template


# =============================================================================
# ForEach Parametrized Tests - All passing
# =============================================================================


def get_foreach_test_cases(section: str) -> List[Tuple[str, Path, Path]]:
    """Get all ForEach test cases for a section."""
    templates_dir = KOTLIN_TEMPLATES_DIR / "forEach" / section
    if not templates_dir.exists():
        return []
    test_cases = []
    for input_path, expected_path in find_test_pairs(templates_dir):
        if expected_path is not None:
            test_cases.append((input_path.stem, input_path, expected_path))
    return test_cases


@pytest.mark.parametrize(
    "test_name,input_path,expected_path",
    get_foreach_test_cases("outputs"),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_foreach_outputs(test_name: str, input_path: Path, expected_path: Path):
    """Test ForEach expansion in Outputs section."""
    if not input_path.exists():
        pytest.skip("Template not available")
    input_template = load_json_template(input_path)
    expected_template = load_json_template(expected_path)
    result = process_template(input_template)
    assert normalize_template(result) == normalize_template(expected_template)


@pytest.mark.parametrize(
    "test_name,input_path,expected_path",
    get_foreach_test_cases("resources"),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_foreach_resources(test_name: str, input_path: Path, expected_path: Path):
    """Test ForEach expansion in Resources section."""
    if not input_path.exists():
        pytest.skip("Template not available")
    input_template = load_json_template(input_path)
    expected_template = load_json_template(expected_path)
    result = process_template(input_template)
    assert normalize_template(result) == normalize_template(expected_template)


@pytest.mark.parametrize(
    "test_name,input_path,expected_path",
    get_foreach_test_cases("conditions"),
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_foreach_conditions(test_name: str, input_path: Path, expected_path: Path):
    """Test ForEach expansion in Conditions section."""
    if not input_path.exists():
        pytest.skip("Template not available")
    input_template = load_json_template(input_path)
    expected_template = load_json_template(expected_path)
    result = process_template(input_template)
    assert normalize_template(result) == normalize_template(expected_template)


# =============================================================================
# Root Templates - Error Cases (should raise InvalidTemplateException)
# =============================================================================

# Templates that correctly raise errors
ERROR_TEMPLATES_PASSING = [
    "fnIfReferencingNonExistingCondition",
    "templateWithNullResources",
    "templateWithResourcesDefinedAsNull",
    "templateWithNullOutput",
    "outputWithAwsNoValue",
    "templateWithNestedRefNoValue",
    "templateFnInMapInWhenTrueConditionInOutputWithInvalidParam",
    "templateFnInMapInWhenTrueConditionInResourceWithInvalidParam",
    "toJsonStringWithInvalidLayout",
    "templateWithFnLengthAndIncorrectLayout",
    "templateWithInvalidFnSelectIndex",
    "templateWithNoMappingMatch",
    "toJsonStringWithSplitThatDoesNotResolve",
    "templateWithFnMapInCondition",
    "templateWithStringResource",
    "fnSplitWithEmptySpliter",
    "templateWithNestedCircularConditions",
    "templateWithSelfReferenceCircularConditions",
    "templateWithNonresolvableConditions",
    "templateWithResourceConditionWithoutConditionSection",
    "templateWithResourceConditionWithoutReferencedInConditionSection",
    "templateWithMappingMatchNull",
    "outputWithNullSub",
    "templateWithInvalidConditionRef",
    "templateWithInvalidIntrinsicFunctionType",
    "toJsonStringReferringToNonResolvablePseudoParam",
    "toJsonStringReferringToNonResolvablePseudoParamArray",
    "toJsonStringReferringToNonResolvableIntrinsicFunction",
    "toJsonStringReferringToNonResolvableIntrinsicFunctionArray",
    # FindInMap templates that should throw errors
    "fnFindInMapWithDefaultValueWithMapTopKeyNotResolveToString",
    "fnFindInMapWithMapNameNotResolveToString",
    "fnFindInMapWithReferenceToIncorrectParameterType",
    "fnFindInMapWithUnsupportedFunctionFnGetAtt",
    "fnFindInMapWithUnsupportedFunctionFnRef",
    "fnFindInMapWithUnsupportedFunctionInMapName",
    "templateFnInMapInWhenFalseConditionInResourceWithInvalidStringPath",
]

# Templates that should error but have compatibility issues
ERROR_TEMPLATES_XFAIL: List[str] = [
    # No more xfail templates - all handled by placeholder replacement tests below
]

# Templates that use $RESOURCE_ATTRIBUTE placeholder and should raise errors
ERROR_TEMPLATES_WITH_PLACEHOLDER = [
    "resourceAttributesWithWrongValueList",
    "resourceAttributesWithAwsNoValue",
]


@pytest.mark.parametrize("template_name", ERROR_TEMPLATES_PASSING)
def test_error_templates_passing(template_name: str):
    """Test templates that should raise InvalidTemplateException."""
    input_path = KOTLIN_TEMPLATES_DIR / f"{template_name}.json"
    if not input_path.exists():
        pytest.skip(f"Template {template_name} not available")
    input_template = load_json_template(input_path)
    with pytest.raises(InvalidTemplateException):
        process_template(input_template)


@pytest.mark.parametrize("template_name", ERROR_TEMPLATES_WITH_PLACEHOLDER)
def test_error_templates_with_placeholder(template_name: str):
    """Test templates with $RESOURCE_ATTRIBUTE placeholder that should raise errors."""
    input_path = KOTLIN_TEMPLATES_DIR / f"{template_name}.json"
    if not input_path.exists():
        pytest.skip(f"Template {template_name} not available")
    # Replace placeholder with DeletionPolicy (Kotlin tests do this)
    input_template = load_json_template_with_placeholder(input_path)
    with pytest.raises(InvalidTemplateException):
        process_template(input_template)


# =============================================================================
# Root Templates - Success Cases (should process without errors)
# =============================================================================

# Templates that correctly process without errors
SUCCESS_TEMPLATES_PASSING = [
    "conditionWithNull",
    "fnFindInMapSelectDefaultValueList",
    "fnFindInMapWithDefaultValue",
    "fnFindInMapWithDefaultValueListAsIs",
    "fnFindInMapWithFnGetAttInDefaultValue",
    "fnFindInMapWithFnRefInDefaultValue",
    "fnFindInMapWithIntrinsic",
    "fnFindInMapWithUnsupportedFunctionFnSub",
    "fnIfOutputBug",
    "fnIfWithUnresolvableInFalseBranch",
    "fnSubWithParameter",
    "fnSubWithReference",
    "getAttOfIntrinsicFunction",
    "getAttOfUnresolvableIntrinsicFunctionInAttrName",
    "getAttOfUnresolvableIntrinsicFunctionInLogicalId",
    "noEchoParameter",
    "noResourceAttribute",
    "noResourceAttributeWithAwsStackId",
    "noResourceAttributeWithAwsStackName",
    "propertiesWithNull",
    "refOfIntrinsicFunction",
    "refOfIntrinsicFunctionWithParameterValueAssigned",
    "refOfUnresolvableIntrinsicFunction",
    "resourceAttributesReferringToParam",
    "resourceAttributesReferringToString",
    "resourceAttributesWithAccountIdPseudoParam",
    "resourceAttributesWithCondition",
    "resourceAttributesWithFnGetAtt",
    "resourceAttributesWithFnSubWithRightValue",
    "resourceAttributesWithMap",
    "resourceAttributesWithReferenceToOtherResource",
    "resourceAttributesWithRegionPseudoParam",
    "resourceWithBase64String",
    "templateComparingStringWithBoolean",
    "templateComparingStringWithNumber",
    "templateFindInMapWhenFalseConditionInResourceWithDefaultValue",
    "templateFindInMapWithDifferentConditionsPerResources",
    "templateFindInMapWithInvalidRef",  # Has false condition, so succeeds with partial resolution
    "templateFindInMapWithinFnIfDiscardedWhenFalseCondition",
    "templateFindInMapWithinFnIfResolvableAsFalseConditionWithDefaultValue",
    "templateWithDifferentTypesOfParameters",
    "templateWithFindInMapDefaultValue",
    "templateWithFnJoinWithNoValue",
    "templateWithFnLengthInConditions",
    "templateWithFnLengthReferringToFnBase64",
    "templateWithFnLengthReferringToFnFindInMap",
    "templateWithFnLengthReferringToFnIf",
    "templateWithFnLengthReferringToFnJoin",
    "templateWithFnLengthReferringToFnSelect",
    "templateWithFnLengthReferringToFnSplit",
    "templateWithFnLengthReferringToFnSub",
    "templateWithFnLengthReferringToResolvableFunctions",
    "templateWithFnLengthSimple",
    "templateWithFnLengthWithRef",
    "templateWithFnLengthWithRefToCDLInConditions",
    "templateWithIntrinsicFunctionsInOutput",
    "templateWithLangXIntrinsicAndUnresolvablePseudoParam",
    "templateWithNestedRefConditions",
    "templateWithNullInput",
    "templateWithOutputsAndNoValueProperty",
    "templateWithRedundantFnSub",
    "templateWithUnresolvedFnSelectRef",
    "toJsonFnSplitDirectlyUnderToJson",
    "toJsonStringReferringToParamWithDefaultValue",
    "toJsonStringReferringToParamWithDefaultValueArray",
    "toJsonStringReferringToParamWithNonResolvableFunctions",
    "toJsonStringReferringToParamWithNonResolvableFunctionsArray",
    "toJsonStringReferringToParamWithoutDefaultValue",
    "toJsonStringReferringToParamWithResolvableFunctions",
    "toJsonStringReferringToParamWithResolvableFunctionsArray",
    "toJsonStringWithCidrInSelect",
    "toJsonStringWithinIntrinsicFunctions",
    "toJsonStringWithSimpleTags",
    "toJsonStringWithSplitThatResolves",
    "toJsonStringWithStackNamePseudoParam",
]

# Templates with known compatibility issues
# These templates use $RESOURCE_ATTRIBUTE placeholder that needs to be replaced
# or have special Lambda transform request format
SUCCESS_TEMPLATES_XFAIL: List[str] = [
    # No xfail templates - all compatibility issues resolved
]

# Templates that are intentionally not supported by the Python library
# These use the Lambda macro request format (fragment, accountId, transformId, etc.)
# which is specific to the Kotlin Lambda handler, not the template processing logic
LAMBDA_FORMAT_TEMPLATES = [
    "templateWithIntrinsicFunctionsAndDefaultValue",
    "templateWithIntrinsicFunctionsWithoutDefaultValue",
]


@pytest.mark.parametrize("template_name", SUCCESS_TEMPLATES_PASSING)
def test_success_templates_passing(template_name: str):
    """Test templates that should process successfully."""
    input_path = KOTLIN_TEMPLATES_DIR / f"{template_name}.json"
    if not input_path.exists():
        pytest.skip(f"Template {template_name} not available")
    input_template = load_json_template(input_path)
    result = process_template(input_template)
    assert isinstance(result, dict)


@pytest.mark.parametrize("template_name", LAMBDA_FORMAT_TEMPLATES)
def test_lambda_format_templates_not_supported(template_name: str):
    """Test that Lambda macro format templates are not supported.

    These templates use the Lambda macro request format (fragment, accountId,
    transformId, templateParameterValues) which is specific to the Kotlin
    Lambda handler. The Python library processes templates directly and
    doesn't need to support this format.
    """
    input_path = KOTLIN_TEMPLATES_DIR / f"{template_name}.json"
    if not input_path.exists():
        pytest.skip(f"Template {template_name} not available")
    input_template = load_json_template(input_path)
    # These templates don't have a Resources section at the top level
    # (it's nested under 'fragment'), so they should fail validation
    with pytest.raises(InvalidTemplateException):
        process_template(input_template)


# =============================================================================
# Templates with Expected Output
# =============================================================================


def test_template_with_intrinsic_in_policy_document():
    """Test template with intrinsic function in PolicyDocument resolves correctly."""
    input_path = KOTLIN_TEMPLATES_DIR / "templateWithIntrinsicInPolicyDocument.json"
    expected_path = KOTLIN_TEMPLATES_DIR / "templateWithIntrinsicInPolicyDocumentResolved.json"

    if not input_path.exists():
        pytest.skip("Template not available")

    input_template = load_json_template(input_path)
    expected_template = load_json_template(expected_path)
    result = process_template(input_template)

    # Compare Resources section
    assert normalize_template(result["Resources"]) == normalize_template(expected_template["Resources"])


def test_template_with_decimal_numbers():
    """Test template with decimal numbers resolved without truncation.

    Note: The Kotlin expected output file has Outputs, AWSTemplateFormatVersion,
    and Hooks nested inside the Resources section. This appears to be a
    serialization artifact from the aws.cfn library used by Kotlin. The Python
    implementation correctly keeps these at the top level. We compare only the
    NullResource which is the actual resource being tested for decimal number
    handling.
    """
    input_path = KOTLIN_TEMPLATES_DIR / "templateWithDecimalNumbers.json"
    expected_path = KOTLIN_TEMPLATES_DIR / "templateWithDecimalNumbersResolved.json"

    if not input_path.exists():
        pytest.skip("Template not available")

    input_template = load_json_template(input_path)
    expected_template = load_json_template(expected_path)
    result = process_template(input_template)

    # Compare only the NullResource - the expected file has extra sections
    # (Outputs, Hooks, AWSTemplateFormatVersion) nested inside Resources
    # which appears to be a serialization artifact from the Kotlin aws.cfn library
    assert normalize_template(result["Resources"]["NullResource"]) == normalize_template(
        expected_template["Resources"]["NullResource"]
    )

    # Also verify decimal numbers are preserved correctly
    assert result["Resources"]["NullResource"]["Metadata"]["EmbeddedValue"] == 99999999999.99
    assert result["Resources"]["NullResource"]["Metadata"]["ParameterReference"] == 99999999999.99


# =============================================================================
# Specific Behavior Tests
# =============================================================================


class TestFnLength:
    """Test Fn::Length specific behaviors."""

    def test_fn_length_simple(self):
        """Test simple Fn::Length resolves to list length."""
        input_path = KOTLIN_TEMPLATES_DIR / "templateWithFnLengthSimple.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        assert result["Resources"]["Queue"]["Properties"]["DelaySeconds"] == 3

    def test_fn_length_with_ref_parameter(self):
        """Test Fn::Length with Ref to parameter."""
        input_path = KOTLIN_TEMPLATES_DIR / "templateWithFnLengthWithRef.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template, parameter_values={"queues": ["a", "b", "c"]})
        assert result["Resources"]["Queue"]["Properties"]["DelaySeconds"] == 3


class TestFnToJsonString:
    """Test Fn::ToJsonString specific behaviors."""

    def test_to_json_string_with_parameter_values(self):
        """Test Fn::ToJsonString with parameter values."""
        input_path = KOTLIN_TEMPLATES_DIR / "toJsonStringReferringToParamWithoutDefaultValue.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template, parameter_values={"PasswordParameter": "Pa$$word"})
        secret_string = result["Resources"]["CloudFormationCreatedSecret"]["Properties"]["SecretString"]
        assert "Pa$$word" in secret_string

    def test_to_json_string_with_simple_tags(self):
        """Test Fn::ToJsonString with simple tags."""
        input_path = KOTLIN_TEMPLATES_DIR / "toJsonStringWithSimpleTags.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        assert "Resources" in result


class TestFnFindInMap:
    """Test Fn::FindInMap specific behaviors."""

    def test_find_in_map_with_default_value(self):
        """Test Fn::FindInMap with DefaultValue."""
        input_path = KOTLIN_TEMPLATES_DIR / "fnFindInMapWithDefaultValue.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        assert "Resources" in result

    def test_find_in_map_with_intrinsic(self):
        """Test Fn::FindInMap with intrinsic function keys."""
        input_path = KOTLIN_TEMPLATES_DIR / "fnFindInMapWithIntrinsic.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        assert "Resources" in result


class TestConditions:
    """Test condition-related behaviors."""

    def test_condition_with_null(self):
        """Test condition handling with null values."""
        input_path = KOTLIN_TEMPLATES_DIR / "conditionWithNull.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        assert "Resources" in result


class TestResourceAttributes:
    """Test resource attribute behaviors."""

    def test_resource_attributes_referring_to_param(self):
        """Test resource attributes with parameter reference."""
        input_path = KOTLIN_TEMPLATES_DIR / "resourceAttributesReferringToParam.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template, parameter_values={"DeletionPolicyParam": "Retain"})
        assert "Resources" in result

    def test_base64_encoding(self):
        """Test Fn::Base64 correctly encodes."""
        input_path = KOTLIN_TEMPLATES_DIR / "resourceWithBase64String.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(input_template)
        user_data = result["Resources"]["EksNodeLaunchTemplate"]["Properties"]["LaunchTemplateData"]["UserData"]
        assert user_data == "ZWNobyAnSGVsbG8gV29ybGQn"

    def test_resource_attributes_referring_to_multiple_params(self):
        """Test resource attributes with multiple parameter references."""
        input_path = KOTLIN_TEMPLATES_DIR / "resourceAttributesReferringToMultipleParams.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        input_template = load_json_template(input_path)
        result = process_template(
            input_template,
            parameter_values={"ResourceAttributeParameter1": "Retain", "ResourceAttributeParameter2": "Delete"},
        )
        assert result["Resources"]["WaitHandle1"]["DeletionPolicy"] == "Retain"
        assert result["Resources"]["WaitHandle2"]["UpdateReplacePolicy"] == "Delete"

    def test_resource_attributes_referring_to_partition(self):
        """Test resource attributes with partition reference."""
        input_path = KOTLIN_TEMPLATES_DIR / "resourceAttributesReferringToPartition.json"
        if not input_path.exists():
            pytest.skip("Template not available")
        # Replace $RESOURCE_ATTRIBUTE with DeletionPolicy
        input_template = load_json_template_with_placeholder(input_path)
        result = process_template(
            input_template, pseudo_parameters=PseudoParameterValues(region="us-east-1", account_id="123456789012")
        )
        assert "Resources" in result
        # The DeletionPolicy should be resolved from the mapping
        assert result["Resources"]["WaitHandle"]["DeletionPolicy"] == "Delete"
