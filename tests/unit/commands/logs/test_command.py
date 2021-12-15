from unittest import TestCase
from unittest.mock import Mock, patch, call, ANY

from parameterized import parameterized

from samcli.commands.logs.command import do_cli


@patch("samcli.commands._utils.experimental.is_experimental_enabled")
@patch("samcli.commands._utils.experimental.update_experimental_context")
class TestLogsCliCommand(TestCase):
    def setUp(self):

        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"
        self.output_dir = "output_dir"
        self.region = "region"
        self.profile = "profile"

    @parameterized.expand(
        [
            (
                True,
                False,
                [],
            ),
            (
                False,
                False,
                [],
            ),
            (
                True,
                False,
                ["cw_log_group"],
            ),
            (
                False,
                False,
                ["cw_log_group", "cw_log_group2"],
            ),
        ]
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
            self.output_dir,
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
            mocked_resource_provider, self.stack_name, self.function_name
        )

        fetch_param = not bool(len(cw_log_group))
        mocked_resource_physical_id_resolver.assert_has_calls([call.get_resource_information(fetch_param)])

        patched_generate_puller.assert_called_with(
            mocked_client_provider,
            mocked_resource_information,
            self.filter_pattern,
            cw_log_group,
            self.output_dir,
            False,
        )

        if tailing:
            mocked_puller.assert_has_calls([call.tail(mocked_start_time, self.filter_pattern)])
        else:
            mocked_puller.assert_has_calls(
                [call.load_time_period(mocked_start_time, mocked_end_time, self.filter_pattern)]
            )
