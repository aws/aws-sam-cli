
from unittest import TestCase
from mock import Mock, patch
from nose_parameterized import parameterized

from samcli.commands.local.lib.sam_base_provider import SamBaseProvider


class TestSamBaseProvider_resolve_parameters(TestCase):

    @parameterized.expand([
        ("AWS::AccountId", "123456789012"),
        ("AWS::Partition", "aws"),
        ("AWS::Region", "us-east-1"),
        ("AWS::StackName", "local"),
        ("AWS::StackId", "arn:aws:cloudformation:us-east-1:123456789012:stack/"
                         "local/51af3dc0-da77-11e4-872e-1234567db123"),
        ("AWS::URLSuffix", "localhost"),
    ])
    def test_with_pseudo_parameters(self, parameter, expected_value):

        template_dict = {
            "Key": {
                "Ref": parameter
            }
        }

        expected_template = {
            "Key": expected_value
        }

        result = SamBaseProvider._resolve_parameters(template_dict, {})
        self.assertEquals(result, expected_template)

    def test_override_pseudo_parameters(self):
        template = {
            "Key": {
                "Ref": "AWS::Region"
            }
        }

        override = {
            "AWS::Region": "someregion"
        }

        expected_template = {
            "Key": "someregion"
        }

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)

    def test_parameter_with_defaults(self):
        override = {}  # No overrides

        template = {
            "Parameters": {
                "Key1": {
                    "Default": "Value1"
                },
                "Key2": {
                    "Default": "Value2"
                },
                "NoDefaultKey3": {}  # No Default
            },

            "Resources": {
                "R1": {"Ref": "Key1"},
                "R2": {"Ref": "Key2"},
                "R3": {"Ref": "NoDefaultKey3"}
            }
        }

        expected_template = {
            "Parameters": {
                "Key1": {
                    "Default": "Value1"
                },
                "Key2": {
                    "Default": "Value2"
                },
                "NoDefaultKey3": {}  # No Default
            },

            "Resources": {
                "R1": "Value1",
                "R2": "Value2",
                "R3": {"Ref": "NoDefaultKey3"}  # No default value. so no subsitution
            }
        }

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)

    def test_override_parameters(self):
        template = {
            "Parameters": {
                "Key1": {
                    "Default": "Value1"
                },
                "Key2": {
                    "Default": "Value2"
                },
                "NoDefaultKey3": {},

                "NoOverrideKey4": {}   # No override Value provided
            },

            "Resources": {
                "R1": {"Ref": "Key1"},
                "R2": {"Ref": "Key2"},
                "R3": {"Ref": "NoDefaultKey3"},
                "R4": {"Ref": "NoOverrideKey4"}
            }
        }

        override = {
            "Key1": "OverrideValue1",
            "Key2": "OverrideValue2",
            "NoDefaultKey3": "OverrideValue3"
        }

        expected_template = {
            "Parameters": {
                "Key1": {
                    "Default": "Value1"
                },
                "Key2": {
                    "Default": "Value2"
                },
                "NoDefaultKey3": {},
                "NoOverrideKey4": {}   # No override Value provided
            },

            "Resources": {
                "R1": "OverrideValue1",
                "R2": "OverrideValue2",
                "R3": "OverrideValue3",
                "R4": {"Ref": "NoOverrideKey4"}
            }
        }

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)

    def test_must_skip_non_ref_intrinsics(self):
        template = {
            "Key1": {"Fn::Sub": ["${AWS::Region}"]},  # Sub is not implemented
            "Key2": {"Ref": "MyParam"}
        }

        override = {"MyParam": "MyValue"}

        expected_template = {
            "Key1": {"Fn::Sub": ["${AWS::Region}"]},
            "Key2": "MyValue"
        }

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)

    def test_must_skip_empty_overrides(self):
        template = {"Key": {"Ref": "Param"}}
        override = None
        expected_template = {"Key": {"Ref": "Param"}}

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)

    def test_must_skip_empty_template(self):
        template = {}
        override = None
        expected_template = {}

        self.assertEquals(SamBaseProvider._resolve_parameters(template, override),
                          expected_template)


class TestSamBaseProvider_get_template(TestCase):

    @patch("samcli.commands.local.lib.sam_base_provider.SamTranslatorWrapper")
    @patch.object(SamBaseProvider, "_resolve_parameters")
    def test_must_run_translator_plugins(self, resolve_params_mock, SamTranslatorWrapperMock):
        translator_instance = SamTranslatorWrapperMock.return_value = Mock()

        template = {"Key": "Value"}
        overrides = {'some': 'value'}

        SamBaseProvider.get_template(template, overrides)

        SamTranslatorWrapperMock.assert_called_once_with(template)
        translator_instance.run_plugins.assert_called_once()
        resolve_params_mock.assert_called_once()
