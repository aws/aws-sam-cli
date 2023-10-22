from parameterized import parameterized
from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.lib.swagger.parser import SwaggerParser
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider


class TestDisableAuthorizerFlagInExtractSwaggerRoute(TestCase):
    @parameterized.expand(
        [("when enabled will not extract authorizers", True), ("when disabled extracts authorizers", False)]
    )
    @patch.object(SwaggerParser, "get_authorizers")
    @patch("samcli.lib.providers.cfn_base_api_provider.LOG.debug")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerParser")
    @patch("samcli.lib.providers.cfn_base_api_provider.SwaggerReader")
    def test_disabled_authorizer_flag(
        self,
        _,
        disable_authorizer,
        mock_reader: Mock,
        mock_parser: Mock,
        mock_debug_log: Mock,
        mock_get_authorizers: Mock,
    ):
        mock_collector = Mock()
        CfnBaseApiProvider.extract_swagger_route(
            stack_path="",
            logical_id="",
            body={},
            uri="",
            binary_media=None,
            collector=mock_collector,
            cwd="",
            event_type="HttpApi",
            disable_authorizer=disable_authorizer,
        )
        mock_get_authorizers.return_value = [{}, {}, {}]

        if disable_authorizer:
            mock_collector.add_authorizers.assert_not_called()

        if not disable_authorizer:
            mock_collector.add_authorizers.assert_called_once()
