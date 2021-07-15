from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.test.command import do_cli


class TestTestCliCommand(TestCase):
    def setUp(self) -> None:
        self.stack_name = "stack_name"
        self.resource_id = "resource_id"
        self.region = "region"
        self.profile = "profile"
        self.config_file = "config_file"
        self.config_env = "config_env"

    @parameterized.expand(
        [
            ("payload", None, False, None, Mock(), None),
            ("payload", None, False, Mock(), None, None),
            ("payload", None, False, Mock(), Mock(), Mock()),
            ("payload", None, False, Mock(), Mock(), None),
            ("payload", None, True, Mock(), Mock(), None),
            (None, "payload_file", False, Mock(), Mock(), None),
            (None, "payload_file", True, Mock(), Mock(), None),
            (None, None, True, Mock(), Mock(), None),
        ]
    )
    @patch("samcli.commands.test.command.LOG")
    @patch("samcli.commands.logs.puller_factory.generate_puller")
    @patch("samcli.commands.logs.logs_context.ResourcePhysicalIdResolver")
    @patch("samcli.lib.test.test_executor_factory.TestExecutorFactory")
    @patch("samcli.lib.test.test_executors.TestExecutionInfo")
    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_with_config")
    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_with_config")
    @patch("samcli.lib.utils.cloudformation.get_resource_summary")
    @patch("sys.stdin")
    def test_test_command(
        self,
        payload,
        payload_file,
        tail,
        given_resource_summary,
        given_test_executor,
        given_execution_exception,
        patched_stdin,
        patched_get_resource_summary,
        patched_get_boto_resource_provider_with_config,
        patched_get_boto_client_provider_with_config,
        patched_test_execution_info,
        patched_test_executor_factory,
        patched_resource_physical_id_resolver,
        patched_generate_puller,
        patched_log,
    ):
        given_client_provider = Mock()
        patched_get_boto_client_provider_with_config.return_value = given_client_provider

        given_resource_provider = Mock()
        patched_get_boto_resource_provider_with_config.return_value = given_resource_provider

        patched_get_resource_summary.return_value = given_resource_summary

        given_test_executor_factory = Mock()
        patched_test_executor_factory.return_value = given_test_executor_factory

        given_test_executor_factory.create_test_executor.return_value = given_test_executor

        given_test_execution_info = Mock()
        patched_test_execution_info.return_value = given_test_execution_info

        given_test_result = Mock(exception=given_execution_exception)
        given_test_result.is_succeeded.return_value = not bool(given_execution_exception)
        if given_test_executor:
            given_test_executor.execute.return_value = given_test_result

        given_resource_physical_id_resolver = Mock()
        patched_resource_physical_id_resolver.return_value = given_resource_physical_id_resolver

        given_puller = Mock()
        patched_generate_puller.return_value = given_puller

        do_cli(
            self.stack_name,
            self.resource_id,
            payload,
            payload_file,
            tail,
            self.region,
            self.profile,
            self.config_file,
            self.config_env,
        )

        patched_get_boto_client_provider_with_config.assert_called_with(region_name=self.region)
        patched_get_boto_resource_provider_with_config.assert_called_with(region_name=self.region)

        patched_get_resource_summary.assert_called_with(given_resource_provider, self.stack_name, self.resource_id)

        if not given_resource_summary:
            # if resource not found it shouldn't go further
            patched_test_executor_factory.assert_not_called()
            return

        patched_test_executor_factory.assert_called_with(given_client_provider)
        given_test_executor_factory.create_test_executor.assert_called_with(given_resource_summary)

        if not given_test_executor:
            # if test executor not found it shouldn't go further
            patched_test_execution_info.assert_not_called()
            return

        # if both payload and payload_file is None, it should use sys.stdin
        if not payload and not payload_file:
            patched_test_execution_info.assert_called_with(payload, patched_stdin)
        else:
            patched_test_execution_info.assert_called_with(payload, payload_file)

        given_test_executor.execute.assert_called_with(given_test_execution_info)

        if given_execution_exception:
            patched_log.error.assert_called_with(
                "Test execution failed with following error", exc_info=given_execution_exception
            )
            patched_log.info.assert_not_called()

        if tail:
            patched_resource_physical_id_resolver.assert_called_with(given_resource_provider, self.stack_name, [])
            patched_generate_puller.assert_called_with(
                given_client_provider,
                given_resource_physical_id_resolver.get_resource_information(),
                include_tracing=True,
            )

            given_puller.tail.assert_called_once()
