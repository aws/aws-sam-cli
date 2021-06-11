from unittest import TestCase
from unittest.mock import Mock, patch, call, ANY

from parameterized import parameterized

from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from samcli.commands.logs.puller_factory import (
    generate_puller,
    generate_file_consumer,
    generate_console_consumer,
    NoPullerGeneratedException,
    generate_consumer,
)


class TestPullerFactory(TestCase):
    @parameterized.expand(
        [
            (None, None, None),
            ("filter_pattern", None, None),
            ("filter_pattern", ["cw_log_groups"], None),
            ("filter_pattern", ["cw_log_groups"], "output_dir"),
            (None, ["cw_log_groups"], "output_dir"),
            (None, None, "output_dir"),
        ]
    )
    @patch("samcli.commands.logs.puller_factory.generate_console_consumer")
    @patch("samcli.commands.logs.puller_factory.generate_file_consumer")
    @patch("samcli.commands.logs.puller_factory.CWLogPuller")
    @patch("samcli.commands.logs.puller_factory.generate_trace_puller")
    @patch("samcli.commands.logs.puller_factory.ObservabilityCombinedPuller")
    def test_generate_puller(
        self,
        param_filter_pattern,
        param_cw_log_groups,
        param_output_dir,
        patched_combined_puller,
        patched_xray_puller,
        patched_cw_log_puller,
        patched_file_consumer,
        patched_console_consumer,
    ):
        mock_logs_client = Mock()
        mock_xray_client = Mock()
        mock_logs_client_generator = lambda: mock_logs_client
        mock_resource_info_list = [
            Mock(resource_type=AWS_LAMBDA_FUNCTION),
            Mock(resource_type=AWS_LAMBDA_FUNCTION),
            Mock(resource_type=AWS_LAMBDA_FUNCTION),
        ]

        mocked_resource_consumers = [Mock() for _ in mock_resource_info_list]
        mocked_cw_specific_consumers = [Mock() for _ in (param_cw_log_groups or [])]
        mocked_consumers = mocked_resource_consumers + mocked_cw_specific_consumers

        # depending on the output_dir param patch file consumer or console consumer
        if param_output_dir:
            patched_file_consumer.side_effect = mocked_consumers
        else:
            patched_console_consumer.side_effect = mocked_consumers

        mocked_xray_puller = Mock()
        patched_xray_puller.return_value = mocked_xray_puller
        mocked_pullers = [Mock() for _ in mocked_consumers]
        mocked_pullers.append(mocked_xray_puller)  # add a mock puller for xray puller
        patched_cw_log_puller.side_effect = mocked_pullers

        mocked_combined_puller = Mock()

        patched_combined_puller.return_value = mocked_combined_puller

        puller = generate_puller(
            mock_logs_client_generator,
            mock_xray_client,
            mock_resource_info_list,
            param_filter_pattern,
            param_cw_log_groups,
            param_output_dir,
            True,
        )

        self.assertEqual(puller, mocked_combined_puller)

        patched_xray_puller.assert_called_once_with(mock_xray_client, param_output_dir)

        patched_cw_log_puller.assert_has_calls(
            [call(mock_logs_client, consumer, ANY, ANY) for consumer in mocked_resource_consumers]
        )

        patched_cw_log_puller.assert_has_calls(
            [call(mock_logs_client, consumer, ANY) for consumer in mocked_cw_specific_consumers]
        )

        patched_combined_puller.assert_called_with(mocked_pullers)

        # depending on the output_dir param assert calls for file consumer or console consumer
        if param_output_dir:
            patched_file_consumer.assert_has_calls([call(param_output_dir, ANY) for _ in mocked_consumers])
        else:
            patched_console_consumer.assert_has_calls([call(param_filter_pattern) for _ in mocked_consumers])

    def test_puller_with_invalid_resource_type(self):
        mock_logs_client = Mock()
        mock_resource_information = Mock()
        mock_resource_information.get_log_group_name.return_value = None

        with self.assertRaises(NoPullerGeneratedException):
            generate_puller(mock_logs_client, None, [mock_resource_information])

    @patch("samcli.commands.logs.puller_factory.generate_console_consumer")
    @patch("samcli.commands.logs.puller_factory.CWLogPuller")
    @patch("samcli.commands.logs.puller_factory.ObservabilityCombinedPuller")
    def test_generate_puller_with_console_with_additional_cw_logs_groups(
        self, patched_combined_puller, patched_cw_log_puller, patched_console_consumer
    ):
        mock_logs_client = Mock()
        mock_logs_client_generator = lambda: mock_logs_client
        mock_cw_log_groups = [Mock(), Mock(), Mock()]

        mocked_consumers = [Mock() for _ in mock_cw_log_groups]
        patched_console_consumer.side_effect = mocked_consumers

        mocked_pullers = [Mock() for _ in mock_cw_log_groups]
        patched_cw_log_puller.side_effect = mocked_pullers

        mocked_combined_puller = Mock()
        patched_combined_puller.return_value = mocked_combined_puller

        puller = generate_puller(mock_logs_client_generator, None, [], additional_cw_log_groups=mock_cw_log_groups)

        self.assertEqual(puller, mocked_combined_puller)

        patched_cw_log_puller.assert_has_calls([call(mock_logs_client, consumer, ANY) for consumer in mocked_consumers])

        patched_combined_puller.assert_called_with(mocked_pullers)

        patched_console_consumer.assert_has_calls([call(None) for _ in mock_cw_log_groups])

    @parameterized.expand(
        [
            ("output_dir",),
            (None,),
        ]
    )
    @patch("samcli.commands.logs.puller_factory.generate_file_consumer")
    @patch("samcli.commands.logs.puller_factory.generate_console_consumer")
    def test_generate_consumer(self, param_output_dir, patched_console_consumer, patched_file_consumer):
        given_filter_pattern = Mock()
        given_resource_name = Mock()

        given_console_consumer = Mock()
        patched_console_consumer.return_value = given_console_consumer
        given_file_consumer = Mock()
        patched_file_consumer.return_value = given_file_consumer

        actual_consumer = generate_consumer(given_filter_pattern, param_output_dir, given_resource_name)

        if param_output_dir:
            patched_file_consumer.assert_called_with(param_output_dir, given_resource_name)
            self.assertEqual(actual_consumer, given_file_consumer)
        else:
            patched_console_consumer.assert_called_with(given_filter_pattern)
            self.assertEqual(actual_consumer, given_console_consumer)

    @patch("samcli.commands.logs.puller_factory.ObservabilityEventConsumerDecorator")
    @patch("samcli.commands.logs.puller_factory.CWJsonFormatter")
    @patch("samcli.commands.logs.puller_factory.CWAddNewLineIfItDoesntExist")
    @patch("samcli.commands.logs.puller_factory.CWFileEventConsumer")
    def test_generate_file_consumer(
        self,
        patched_event_consumer,
        patched_new_line_mapper,
        patched_json_formatter,
        patched_decorated_consumer,
    ):
        mock_output_dir = Mock()
        mock_file_prefix = Mock()

        expected_consumer = Mock()
        patched_decorated_consumer.return_value = expected_consumer

        expected_event_consumer = Mock()
        patched_event_consumer.return_value = expected_event_consumer

        expected_new_line_mapper = Mock()
        patched_new_line_mapper.return_value = expected_new_line_mapper

        expected_json_formatter = Mock()
        patched_json_formatter.return_value = expected_json_formatter

        consumer = generate_file_consumer(mock_output_dir, mock_file_prefix)

        self.assertEqual(expected_consumer, consumer)

        patched_decorated_consumer.assert_called_with(
            [expected_json_formatter, expected_new_line_mapper], expected_event_consumer
        )
        patched_event_consumer.assert_called_with(mock_output_dir, mock_file_prefix)
        patched_json_formatter.assert_called_once()
        patched_new_line_mapper.assert_called_once()

    @patch("samcli.commands.logs.puller_factory.Colored")
    @patch("samcli.commands.logs.puller_factory.ObservabilityEventConsumerDecorator")
    @patch("samcli.commands.logs.puller_factory.CWColorizeErrorsFormatter")
    @patch("samcli.commands.logs.puller_factory.CWJsonFormatter")
    @patch("samcli.commands.logs.puller_factory.CWKeywordHighlighterFormatter")
    @patch("samcli.commands.logs.puller_factory.CWPrettyPrintFormatter")
    @patch("samcli.commands.logs.puller_factory.CWAddNewLineIfItDoesntExist")
    @patch("samcli.commands.logs.puller_factory.CWConsoleEventConsumer")
    def test_generate_console_consumer(
        self,
        patched_event_consumer,
        patched_new_line_mapper,
        patched_pretty_formatter,
        patched_highlighter,
        patched_json_formatter,
        patched_errors_formatter,
        patched_decorated_consumer,
        patched_colored,
    ):
        mock_filter_pattern = Mock()

        expected_colored = Mock()
        patched_colored.return_value = expected_colored

        expected_errors_formatter = Mock()
        patched_errors_formatter.return_value = expected_errors_formatter

        expected_json_formatter = Mock()
        patched_json_formatter.return_value = expected_json_formatter

        expected_highlighter = Mock()
        patched_highlighter.return_value = expected_highlighter

        expected_pretty_formatter = Mock()
        patched_pretty_formatter.return_value = expected_pretty_formatter

        expected_new_line_mapper = Mock()
        patched_new_line_mapper.return_value = expected_new_line_mapper

        expected_event_consumer = Mock()
        patched_event_consumer.return_value = expected_event_consumer

        expected_consumer = Mock()
        patched_decorated_consumer.return_value = expected_consumer

        consumer = generate_console_consumer(mock_filter_pattern)

        self.assertEqual(expected_consumer, consumer)

        patched_colored.assert_called_once()
        patched_event_consumer.assert_called_once()
        patched_new_line_mapper.assert_called_once()
        patched_pretty_formatter.assert_called_with(expected_colored)
        patched_highlighter.assert_called_with(expected_colored, mock_filter_pattern)
        patched_json_formatter.assert_called_once()
        patched_errors_formatter.assert_called_with(expected_colored)

        patched_decorated_consumer.assert_called_with(
            [
                expected_errors_formatter,
                expected_json_formatter,
                expected_highlighter,
                expected_pretty_formatter,
                expected_new_line_mapper,
            ],
            expected_event_consumer,
        )
