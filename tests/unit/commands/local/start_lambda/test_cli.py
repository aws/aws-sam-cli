from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.local.start_lambda.cli import do_cli as start_lambda_cli
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.commands.local.cli_common.user_exceptions import UserException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.local.docker.exceptions import ContainerNotStartableException
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError, InvalidIntermediateImageError
from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported


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
        self.warm_containers = None
        self.shutdown = True
        self.debug_function = None
        self.region_name = "region"
        self.profile = "profile"

        self.ctx_mock = Mock()
        self.ctx_mock.region = self.region_name
        self.ctx_mock.profile = self.profile

        self.host = "host"
        self.port = 123

        self.container_host = "localhost"
        self.container_host_interface = "127.0.0.1"
        self.invoke_image = ()
        self.hook_name = None

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.lib.local_lambda_service.LocalLambdaService")
    def test_cli_must_setup_context_and_start_service(self, local_lambda_service_mock, invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        service_mock = Mock()
        local_lambda_service_mock.return_value = service_mock

        self.warm_containers = None
        self.debug_function = None
        self.call_cli()

        invoke_context_mock.assert_called_with(
            template_file=self.template,
            function_identifier=None,
            env_vars_file=self.env_vars,
            container_env_vars_file=self.container_env_vars,
            docker_volume_basedir=self.docker_volume_basedir,
            docker_network=self.docker_network,
            log_file=self.log_file,
            skip_pull_image=self.skip_pull_image,
            debug_ports=self.debug_ports,
            debug_args=self.debug_args,
            debugger_path=self.debugger_path,
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
            invoke_images={},
        )

        local_lambda_service_mock.assert_called_with(lambda_invoke_context=context_mock, port=self.port, host=self.host)

        service_mock.start.assert_called_with()

    @parameterized.expand(
        [
            (InvalidSamDocumentException("bad template"), "bad template"),
            (
                InvalidLayerReference(),
                "Layer References need to be of type " "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'",
            ),
            (DebuggingNotSupported("Debugging not supported"), "Debugging not supported"),
        ]
    )
    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_invalid_sam_template(
        self, exeception_to_raise, execption_message, invoke_context_mock
    ):
        invoke_context_mock.side_effect = exeception_to_raise

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = execption_message
        self.assertEqual(msg, expected)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_invalid_env_vars(self, invoke_context_mock):
        invoke_context_mock.side_effect = OverridesNotWellDefinedError("bad env vars")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "bad env vars"
        self.assertEqual(msg, expected)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_invalid_imageuri(self, invoke_context_mock):
        invoke_context_mock.side_effect = InvalidIntermediateImageError("invalid imageuri")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "invalid imageuri"
        self.assertEqual(msg, expected)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    def test_must_raise_user_exception_on_no_free_ports(self, invoke_context_mock):
        invoke_context_mock.side_effect = ContainerNotStartableException("no free ports on host to bind with container")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "no free ports on host to bind with container"
        self.assertEqual(msg, expected)

    def call_cli(self):
        start_lambda_cli(
            ctx=self.ctx_mock,
            host=self.host,
            port=self.port,
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
            hook_name=self.hook_name,
        )
