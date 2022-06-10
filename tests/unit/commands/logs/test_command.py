import itertools
from unittest import TestCase
from unittest.mock import Mock, patch, call

import pytest
from botocore.exceptions import ClientError
from click.testing import CliRunner
from parameterized import parameterized

from samcli.commands.logs.command import do_cli, cli
from samcli.lib.observability.util import OutputOption


@patch("samcli.commands._utils.experimental.is_experimental_enabled")
@patch("samcli.commands._utils.experimental.update_experimental_context")
class TestLogsCliCommand(TestCase):
    def setUp(self):

        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"
        self.region = "region"
        self.profile = "profile"

    @parameterized.expand(
        itertools.product(
            [True, False], [True, False], [[], ["cw_log_group"], ["cw_log_group", "cw_log_group2"]], ["text", "json"]
        )
    )
    @patch("samcli.commands.logs.puller_factory.generate_puller")
    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver")
    @patch("samcli.commands.logs.logs_context.parse_time")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    def test_logs_command(
        self,
        tailing,
        include_tracing,
        cw_log_group,
        output,
        patched_boto_resource_provider,
        patched_boto_client_provider,
        patched_parse_time,
        patched_resource_physical_id_resolver,
        patched_generate_puller,
        patched_is_experimental_enabled,
        patched_update_experimental_context,
    ):
        mocked_start_time = Mock()
        mocked_end_time = Mock()
        patched_parse_time.side_effect = [mocked_start_time, mocked_end_time]

        mocked_resource_physical_id_resolver = Mock()
        mocked_resource_information = Mock()
        mocked_resource_physical_id_resolver.get_resource_information.return_value = mocked_resource_information
        patched_resource_physical_id_resolver.return_value = mocked_resource_physical_id_resolver

        mocked_puller = Mock()
        patched_generate_puller.return_value = mocked_puller

        mocked_client_provider = Mock()
        patched_boto_client_provider.return_value = mocked_client_provider

        mocked_resource_provider = Mock()
        patched_boto_resource_provider.return_value = mocked_resource_provider

        do_cli(
            self.function_name,
            self.stack_name,
            self.filter_pattern,
            tailing,
            include_tracing,
            self.start_time,
            self.end_time,
            cw_log_group,
            output,
            self.region,
            self.profile,
        )

        patched_parse_time.assert_has_calls(
            [
                call(self.start_time, "start-time"),
                call(self.end_time, "end-time"),
            ]
        )

        patched_boto_client_provider.assert_called_with(region=self.region, profile=self.profile)
        patched_boto_resource_provider.assert_called_with(region=self.region, profile=self.profile)

        patched_resource_physical_id_resolver.assert_called_with(
            mocked_resource_provider, mocked_client_provider, self.stack_name, self.function_name
        )

        fetch_param = not bool(len(cw_log_group))
        mocked_resource_physical_id_resolver.assert_has_calls([call.get_resource_information(fetch_param)])

        patched_generate_puller.assert_called_with(
            mocked_client_provider,
            mocked_resource_information,
            self.filter_pattern,
            cw_log_group,
            OutputOption(output),
            include_tracing,
        )

        if tailing:
            mocked_puller.assert_has_calls([call.tail(mocked_start_time, self.filter_pattern)])
        else:
            mocked_puller.assert_has_calls(
                [call.load_time_period(mocked_start_time, mocked_end_time, self.filter_pattern)]
            )

    def test_without_stack_name_or_cw_log_group(
        self, patched_is_experimental_enabled, patched_update_experimental_context
    ):
        cli_runner = CliRunner()
        result = cli_runner.invoke(cli, [])
        self.assertIn("Please provide '--stack-name' or '--cw-log-group'", result.output)

    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver.get_resource_information")
    @patch("samcli.commands.logs.puller_factory.generate_puller")
    def test_with_stack_name_but_without_cw_log_group_should_succeed(
        self,
        patched_generate_puller,
        patched_get_resource_information,
        patched_is_experimental_enabled,
        patched_update_experimental_context,
    ):
        cli_runner = CliRunner()
        cli_runner.invoke(cli, ["--stack-name", "abcdef"])
        patched_get_resource_information.assert_called_with(True)
        patched_generate_puller.assert_called_once()

    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver.get_resource_information")
    @patch("samcli.commands.logs.puller_factory.generate_puller")
    def test_with_cw_log_group_but_without_stack_name_should_succeed(
        self,
        patched_generate_puller,
        patched_get_resource_information,
        patched_is_experimental_enabled,
        patched_update_experimental_context,
    ):
        cli_runner = CliRunner()
        cli_runner.invoke(cli, ["--cw-log-group", "abcdef"])
        patched_get_resource_information.assert_called_with(False)
        patched_generate_puller.assert_called_once()

    def test_with_name_but_without_stack_name_should_fail(
        self, patched_is_experimental_enabled, patched_update_experimental_context
    ):
        cli_runner = CliRunner()
        result = cli_runner.invoke(cli, ["--name", "abcdef"])
        self.assertIn("Missing option. Please provide '--stack-name' when using '--name' option", result.output)

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver.get_resource_information")
    def test_invalid_stack_name_should_fail(
        self, patched_get_resource_information, patched_is_experimental_enabled, patched_update_experimental_context
    ):
        patched_get_resource_information.side_effect = ClientError(
            {"Error": {"Code": "ValidationError"}}, "ListStackResources"
        )
        self._caplog.set_level(100000)
        cli_runner = CliRunner()
        invalid_stack_name = "my-invalid-stack-name"
        result = cli_runner.invoke(cli, ["--stack-name", invalid_stack_name, "--region", "us-west-2"])
        self.assertIn(
            f"Invalid --stack-name parameter. Stack with id '{invalid_stack_name}' does not exist", result.output
        )
