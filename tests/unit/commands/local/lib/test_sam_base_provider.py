from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable


class TestSamBaseProvider_get_template(TestCase):
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
        SamTranslatorWrapperMock.assert_called_once_with(template, parameter_values=called_parameter_values)
        translator_instance.run_plugins.assert_called_once()
