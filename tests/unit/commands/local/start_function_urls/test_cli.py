"""
Unit test for `start-function-urls` CLI
"""

from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock
from click.testing import CliRunner

from parameterized import parameterized

from samcli.commands.exceptions import UserException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
from samcli.commands.local.cli_common.invoke_context import DockerIsNotReachableException
from samcli.local.docker.exceptions import ContainerNotStartableException


class TestCli(TestCase):
    def setUp(self):
        self.template = "template"
        self.env_vars = "env-vars"
        self.debug_ports = [123]
        self.debug_args = "args"
        self.debugger_path = "/test/path"
        self.container_env_vars = "container-env-vars"
        self.docker_volume_basedir = "basedir"
        self.docker_network = "network"
        self.log_file = "logfile"
        self.skip_pull_image = True
        self.parameter_overrides = {}
        self.layer_cache_basedir = "/some/layers/path"
        self.force_image_build = True
        self.shutdown = True
        self.region_name = "region"
        self.profile = "profile"

        self.warm_containers = None
        self.debug_function = None

        self.ctx_mock = Mock()
        self.ctx_mock.region = self.region_name
        self.ctx_mock.profile = self.profile

        self.host = "127.0.0.1"
        self.port_range = "3001-3010"
        self.function_name = None
        self.port = None
        self.disable_authorizer = False
        self.add_host = []

        self.container_host = "localhost"
        self.container_host_interface = "127.0.0.1"
        self.invoke_image = ()
        self.no_mem_limit = False

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_must_setup_context_and_start_all_services(self, service_mock, invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        manager_mock = Mock()
        service_mock.return_value = manager_mock

        self.call_cli()

        invoke_context_mock.assert_called_with(
            template_file=self.template,
            function_identifier=None,
            env_vars_file=self.env_vars,
            docker_volume_basedir=self.docker_volume_basedir,
            docker_network=self.docker_network,
            log_file=self.log_file,
            skip_pull_image=self.skip_pull_image,
            debug_ports=self.debug_ports,
            debug_args=self.debug_args,
            debugger_path=self.debugger_path,
            container_env_vars_file=self.container_env_vars,
            parameter_overrides=self.parameter_overrides,
            layer_cache_basedir=self.layer_cache_basedir,
            force_image_build=self.force_image_build,
            aws_region=self.region_name,
            aws_profile=self.profile,
            warm_container_initialization_mode=self.warm_containers,
            debug_function=self.debug_function,
            shutdown=self.shutdown,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            add_host=self.add_host,
            invoke_images={},
            no_mem_limit=self.no_mem_limit,
        )

        service_mock.assert_called_with(
            lambda_invoke_context=context_mock,
            port_range=(3001, 3010),
            host=self.host,
            disable_authorizer=self.disable_authorizer,
        )

        manager_mock.start_all.assert_called_with()

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_must_start_specific_function_when_provided(self, service_mock, invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        manager_mock = Mock()
        service_mock.return_value = manager_mock

        self.function_name = "MyFunction"
        self.port = 3005

        self.call_cli()

        manager_mock.start_function.assert_called_with("MyFunction", 3005)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_must_raise_if_no_function_urls_defined(self, service_mock, invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        manager_mock = Mock()
        service_mock.return_value = manager_mock

        from samcli.commands.local.lib.exceptions import NoFunctionUrlsDefined

        manager_mock.start_all.side_effect = NoFunctionUrlsDefined("no function urls")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        self.assertIn("no function urls", msg)

    @parameterized.expand(
        [
            (InvalidSamDocumentException("bad template"), "bad template"),
            (OverridesNotWellDefinedError("bad env vars"), "bad env vars"),
        ]
    )
    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_invalid_inputs(
        self, exception_to_raise, exception_message, invoke_context_mock
    ):
        invoke_context_mock.side_effect = exception_to_raise

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        self.assertEqual(msg, exception_message)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_container_errors(self, invoke_context_mock):
        invoke_context_mock.side_effect = ContainerNotStartableException("no free ports")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        self.assertIn("no free ports", msg)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_with_single_port_range(self, service_mock, invoke_context_mock):
        """Test CLI with single port (no range)"""
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        # Test with single port (no dash)
        self.port_range = "3001"

        manager_mock = Mock()
        service_mock.return_value = manager_mock

        self.call_cli()

        # Should parse as 3001-3011 (single port + 10)
        service_mock.assert_called_with(
            lambda_invoke_context=context_mock,
            host=self.host,
            port_range=(3001, 3011),
            disable_authorizer=self.disable_authorizer,
        )

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_cli_with_docker_not_reachable(self, invoke_context_mock):
        """Test CLI when Docker is not reachable"""

        # Mock Docker not reachable exception
        invoke_context_mock.return_value.__enter__.side_effect = DockerIsNotReachableException("Docker not running")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        self.assertIn("Docker not running", str(context.exception))
        self.assertEqual(context.exception.wrapped_from, "DockerIsNotReachableException")

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_with_keyboard_interrupt(self, service_mock, invoke_context_mock):
        """Test CLI handles KeyboardInterrupt gracefully"""
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        manager_mock = Mock()
        service_mock.return_value = manager_mock
        manager_mock.start_all.side_effect = KeyboardInterrupt()

        # Should not raise, just log and exit
        self.call_cli()

        # Verify start_all was called before interrupt
        manager_mock.start_all.assert_called_once()

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_with_generic_exception(self, service_mock, invoke_context_mock):
        """Test CLI handles generic exceptions"""
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        manager_mock = Mock()
        service_mock.return_value = manager_mock
        manager_mock.start_all.side_effect = RuntimeError("Something went wrong")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        self.assertIn("Error starting Function URL services", str(context.exception))
        self.assertIn("Something went wrong", str(context.exception))
        self.assertEqual(context.exception.wrapped_from, "RuntimeError")

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_function_url_service.LocalFunctionUrlService")
    def test_cli_with_no_context(self, service_mock, invoke_context_mock):
        """Test CLI with no context (ctx=None)"""
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        # Set ctx to None to test the None check
        self.ctx_mock = None

        manager_mock = Mock()
        service_mock.return_value = manager_mock

        self.call_cli()

        # Should pass None for aws_region and aws_profile
        invoke_context_mock.assert_called_once()
        call_kwargs = invoke_context_mock.call_args[1]
        self.assertIsNone(call_kwargs["aws_region"])
        self.assertIsNone(call_kwargs["aws_profile"])

    def call_cli(self):
        from samcli.commands.local.start_function_urls.cli import do_cli as start_function_urls_cli

        start_function_urls_cli(
            ctx=self.ctx_mock,
            host=self.host,
            port_range=self.port_range,
            function_name=self.function_name,
            port=self.port,
            disable_authorizer=self.disable_authorizer,
            template=self.template,
            env_vars=self.env_vars,
            debug_port=self.debug_ports,
            debug_args=self.debug_args,
            debugger_path=self.debugger_path,
            container_env_vars=self.container_env_vars,
            docker_volume_basedir=self.docker_volume_basedir,
            docker_network=self.docker_network,
            log_file=self.log_file,
            skip_pull_image=self.skip_pull_image,
            parameter_overrides=self.parameter_overrides,
            layer_cache_basedir=self.layer_cache_basedir,
            force_image_build=self.force_image_build,
            warm_containers=self.warm_containers,
            debug_function=self.debug_function,
            shutdown=self.shutdown,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_image=self.invoke_image,
            add_host=self.add_host,
            no_mem_limit=self.no_mem_limit,
        )
