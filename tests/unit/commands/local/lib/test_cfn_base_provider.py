from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider


class TestDisableAuthorizerFlagInExtractSwaggerRoute(TestCase):

    @patch("samcli.lib.providers.cfn_base_api_provider.LOG.debug")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerParser")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerReader")
    def test_disable_authorizer_flag_when_enabled_skips_authorizer_extraction(self, mock_reader: Mock, mock_parser: Mock, mock_debug_log: Mock):
        mock_collector = Mock()

        CfnBaseApiProvider.extract_swagger_route(stack_path="", logical_id="", body={}, uri="", binary_media=None, collector=mock_collector, cwd="", event_type="HttpApi", disable_authorizer=True)
        assert "Found '%s' authorizers in resource" not in mock_debug_log.call_args[0]

    @patch.object(SwaggerParser, "get_authorizers")
    @patch("samcli.lib.providers.cfn_base_api_provider.LOG.debug")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerParser")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerReader")
    def test_disable_authorizer_flag_when_disabled_extracts_authorizers(self, mock_reader: Mock, mock_parser: Mock, mock_debug_log: Mock, mock_get_authorizers: Mock):
        mock_collector = Mock()
        mock_get_authorizers.return_value = [{}, {}, {}]

        CfnBaseApiProvider.extract_swagger_route(stack_path="", logical_id="", body={}, uri="", binary_media=None, collector=mock_collector, cwd="", event_type="HttpApi", disable_authorizer=False)
        mock_debug_log.assert_any_call("Found '%s' authorizers in resource '%s'", 0, '')