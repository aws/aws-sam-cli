"""Tests for samcli.lib.cfn_language_extensions.utils — shared helpers."""

from unittest import TestCase

from samcli.lib.cfn_language_extensions.models import ParsedTemplate, ResolutionMode, TemplateProcessingContext
from samcli.lib.cfn_language_extensions.utils import (
    derive_partition,
    derive_url_suffix,
    is_foreach_key,
    is_sam_generated_mapping,
    is_unresolved_param_or_pseudo_ref,
    iter_regular_resources,
)


class TestDerivePartition(TestCase):
    def test_standard_region(self):
        self.assertEqual(derive_partition("us-east-1"), "aws")

    def test_china_region(self):
        self.assertEqual(derive_partition("cn-north-1"), "aws-cn")

    def test_govcloud_region(self):
        self.assertEqual(derive_partition("us-gov-west-1"), "aws-us-gov")


class TestDeriveUrlSuffix(TestCase):
    def test_standard_region(self):
        self.assertEqual(derive_url_suffix("us-west-2"), "amazonaws.com")

    def test_china_region(self):
        self.assertEqual(derive_url_suffix("cn-northwest-1"), "amazonaws.com.cn")


class TestIsForeachKey(TestCase):
    def test_valid_foreach_key(self):
        self.assertTrue(is_foreach_key("Fn::ForEach::Loop"))

    def test_regular_key(self):
        self.assertFalse(is_foreach_key("MyResource"))

    def test_non_string(self):
        self.assertFalse(is_foreach_key(123))


class TestIterRegularResources(TestCase):
    def test_skips_foreach_and_non_dict(self):
        template = {
            "Resources": {
                "Fn::ForEach::Loop": ["X", ["A"], {}],
                "Good": {"Type": "AWS::SNS::Topic"},
                "BadValue": "not a dict",
            }
        }
        result = list(iter_regular_resources(template))
        self.assertEqual(result, [("Good", {"Type": "AWS::SNS::Topic"})])

    def test_empty_resources(self):
        self.assertEqual(list(iter_regular_resources({"Resources": {}})), [])

    def test_missing_resources(self):
        self.assertEqual(list(iter_regular_resources({})), [])


class TestIsSamGeneratedMapping(TestCase):
    def test_bare_prefix_no_match(self):
        self.assertFalse(is_sam_generated_mapping("SAMCodeUri"))

    def test_lowercase_after_prefix_no_match(self):
        # "services" starts lowercase after a prefix that doesn't match any known prefix
        self.assertFalse(is_sam_generated_mapping("SAMservices"))

    def test_layers_prefix_matches(self):
        self.assertTrue(is_sam_generated_mapping("SAMLayersServices"))

    def test_layers_digit_matches(self):
        self.assertTrue(is_sam_generated_mapping("SAMLayers1stBatch"))


class TestIsUnresolvedParamOrPseudoRef(TestCase):
    def _ctx(self, parameters=None) -> TemplateProcessingContext:
        return TemplateProcessingContext(
            fragment={"Resources": {}},
            resolution_mode=ResolutionMode.PARTIAL,
            parsed_template=ParsedTemplate(parameters=parameters or {}),
        )

    def test_ref_to_declared_parameter(self):
        ctx = self._ctx(parameters={"Stage": {"Type": "String"}})
        self.assertTrue(is_unresolved_param_or_pseudo_ref({"Ref": "Stage"}, ctx))

    def test_ref_to_pseudo_parameter(self):
        ctx = self._ctx()
        self.assertTrue(is_unresolved_param_or_pseudo_ref({"Ref": "AWS::Region"}, ctx))

    def test_ref_to_resource_returns_false(self):
        ctx = self._ctx()  # No "Queue" parameter declared.
        self.assertFalse(is_unresolved_param_or_pseudo_ref({"Ref": "Queue"}, ctx))

    def test_getatt_returns_false(self):
        ctx = self._ctx()
        self.assertFalse(is_unresolved_param_or_pseudo_ref({"Fn::GetAtt": ["Q", "Arn"]}, ctx))

    def test_non_dict_returns_false(self):
        ctx = self._ctx()
        self.assertFalse(is_unresolved_param_or_pseudo_ref("Stage", ctx))
        self.assertFalse(is_unresolved_param_or_pseudo_ref(["Ref", "Stage"], ctx))
        self.assertFalse(is_unresolved_param_or_pseudo_ref(None, ctx))

    def test_multi_key_dict_returns_false(self):
        ctx = self._ctx(parameters={"Stage": {"Type": "String"}})
        self.assertFalse(is_unresolved_param_or_pseudo_ref({"Ref": "Stage", "extra": 1}, ctx))

    def test_non_string_ref_target_returns_false(self):
        ctx = self._ctx()
        self.assertFalse(is_unresolved_param_or_pseudo_ref({"Ref": 123}, ctx))

    def test_no_parsed_template_only_pseudo_matches(self):
        ctx = TemplateProcessingContext(fragment={"Resources": {}}, resolution_mode=ResolutionMode.PARTIAL)
        self.assertTrue(is_unresolved_param_or_pseudo_ref({"Ref": "AWS::Region"}, ctx))
        self.assertFalse(is_unresolved_param_or_pseudo_ref({"Ref": "Stage"}, ctx))
