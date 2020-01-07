from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver


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

        SamTranslatorWrapperMock.assert_called_once_with(template)
        translator_instance.run_plugins.assert_called_once()
