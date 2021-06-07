from unittest import TestCase
from unittest.mock import Mock, patch, call, ANY

from parameterized import parameterized

from samcli.commands.logs.command import do_cli


class TestLogsCliCommand(TestCase):
    def setUp(self):

        self.function_name = "name"
        self.stack_name = "stack name"
        self.filter_pattern = "filter"
        self.start_time = "start"
        self.end_time = "end"
        self.output_dir = "output_dir"
        self.region = "region"

    @parameterized.expand(
        [
            (
                True,
                [],
            ),
            (
                False,
                [],
            ),
            (
                True,
                ["cw_log_group"],
            ),
            (
                False,
                ["cw_log_group", "cw_log_group2"],
            ),
        ]
    )
    @patch("samcli.commands.logs.puller_factory.generate_puller")
    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver")
    @patch("boto3.resource")
    @patch("samcli.commands.logs.logs_context.parse_time")
    @patch("samcli.lib.utils.botoconfig.get_boto_config_with_user_agent")
    def test_logs_command(
        self,
        tailing,
        cw_log_group,
        patched_config_generator,
        patched_parse_time,
        patched_resource,
        patched_resource_physical_id_resolver,
        patched_generate_puller,
    ):
        mocked_start_time = Mock()
        mocked_end_time = Mock()
        patched_parse_time.side_effect = [mocked_start_time, mocked_end_time]

        mocked_cfn_resource = Mock()
        patched_resource.return_value = mocked_cfn_resource

        mocked_resource_physical_id_resolver = Mock()
        mocked_resource_information = Mock()
        mocked_resource_physical_id_resolver.get_resource_information.return_value = mocked_resource_information
        patched_resource_physical_id_resolver.return_value = mocked_resource_physical_id_resolver

        mocked_puller = Mock()
        patched_generate_puller.return_value = mocked_puller

        mocked_config = Mock()
        patched_config_generator.return_value = mocked_config

        do_cli(
            self.function_name,
            self.stack_name,
            self.filter_pattern,
            tailing,
            self.start_time,
            self.end_time,
            self.output_dir,
            cw_log_group,
            self.region,
        )

        patched_parse_time.assert_has_calls(
            [
                call(self.start_time, "start-time"),
                call(self.end_time, "end-time"),
            ]
        )

        patched_config_generator.assert_called_with(region_name=self.region)

        patched_resource.assert_has_calls(
            [
                call.resource("cloudformation", config=mocked_config),
            ]
        )

        patched_resource_physical_id_resolver.assert_called_with(
            mocked_cfn_resource, self.stack_name, self.function_name
        )

        fetch_param = not bool(len(cw_log_group))
        mocked_resource_physical_id_resolver.assert_has_calls([call.get_resource_information(fetch_param)])

        patched_generate_puller.assert_called_with(
            ANY, mocked_resource_information, self.filter_pattern, cw_log_group, self.output_dir
        )

        if tailing:
            mocked_puller.assert_has_calls([call.tail(mocked_start_time, self.filter_pattern)])
        else:
            mocked_puller.assert_has_calls(
                [call.load_time_period(mocked_start_time, mocked_end_time, self.filter_pattern)]
            )
