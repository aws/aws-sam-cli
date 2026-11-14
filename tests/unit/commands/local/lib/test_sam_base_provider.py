from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestSamBaseProvider_get_template(TestCase):
    def test_environment_sub_preserves_backslashes(self):
        template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Parameters": {"DataRoot": {"Type": "String", "Default": r"C:\project\data"}},
            "Resources": {
                "ExampleFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Runtime": "python3.12",
                        "Handler": "index.handler",
                        "InlineCode": 'def handler(event, context): return "ok"',
                        "Environment": {"Variables": {"DATA_PATH": {"Fn::Sub": r"${DataRoot}\cache"}}},
                    },
                }
            },
        }

        result = SamBaseProvider.get_template(template, {})

        self.assertEqual(
            result["Resources"]["ExampleFunction"]["Properties"]["Environment"]["Variables"]["DATA_PATH"],
            r"C:\project\data\cache",
        )

    @patch("samcli.lib.providers.sam_base_provider.ResourceMetadataNormalizer")
    @patch("samcli.lib.providers.sam_base_provider.SamTranslatorWrapper")
    @patch.object(IntrinsicResolver, "resolve_template")
    def test_must_run_translator_plugins(
        self, resolve_template_mock, SamTranslatorWrapperMock, resource_metadata_normalizer_patch
    ):
        resource_metadata_normalizer_patch.normalize.return_value = True
        resolve_template_mock.return_value = {}
        translator_instance = SamTranslatorWrapperMock.return_value = Mock()

        template = {"Key": "Value"}
        overrides = {"some": "value"}

        SamBaseProvider.get_template(template, overrides)
        called_parameter_values = IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES.copy()
        called_parameter_values.update(overrides)
        SamTranslatorWrapperMock.assert_called_once_with(
            template, parameter_values=called_parameter_values, language_extension_result=None
        )
        translator_instance.run_plugins.assert_called_once()
