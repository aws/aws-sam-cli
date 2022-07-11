"""
Tests Local Invoke CLI
"""

from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized, param

from samcli.local.docker.exceptions import ContainerNotStartableException
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.exceptions import UserException
from samcli.commands.local.invoke.cli import do_cli as invoke_cli, _get_event as invoke_cli_get_event
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError, InvalidIntermediateImageError
from samcli.local.docker.manager import DockerImagePullFailedException
from samcli.local.docker.lambda_debug_settings import DebuggingNotSupported


STDIN_FILE_NAME = "-"


class TestCli(TestCase):
    def setUp(self):
        self.function_id = "id"
        self.template = "template"
        self.eventfile = "eventfile"
        self.env_vars = "env-vars"
        self.container_env_vars = "debug-env-vars"
        self.debug_ports = [123]
        self.debug_args = "args"
        self.debugger_path = "/test/path"
        self.docker_volume_basedir = "basedir"
        self.docker_network = "network"
        self.log_file = "logfile"
        self.skip_pull_image = True
        self.no_event = True
        self.parameter_overrides = {}
        self.layer_cache_basedir = "/some/layers/path"
        self.force_image_build = True
        self.shutdown = False
        self.region_name = "region"
        self.profile = "profile"
        self.container_host = "localhost"
        self.container_host_interface = "127.0.0.1"
        self.invoke_image = ("amazon/aws-sam-cli-emulation-image-python3.6",)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_cli_must_setup_context_and_invoke(self, get_event_mock, InvokeContextMock):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock

        invoke_cli(
            ctx=ctx_mock,
            function_identifier=self.function_id,
            template=self.template,
            event=self.eventfile,
            no_event=self.no_event,
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
            shutdown=self.shutdown,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_image=self.invoke_image,
        )

        InvokeContextMock.assert_called_with(
            template_file=self.template,
            function_identifier=self.function_id,
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
            shutdown=self.shutdown,
            aws_region=self.region_name,
            aws_profile=self.profile,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_images={None: "amazon/aws-sam-cli-emulation-image-python3.6"},
        )

        context_mock.local_lambda_runner.invoke.assert_called_with(
            context_mock.function_identifier, event=event_data, stdout=context_mock.stdout, stderr=context_mock.stderr
        )
        get_event_mock.assert_called_with(self.eventfile)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_cli_must_invoke_with_no_event(self, get_event_mock, InvokeContextMock):
        self.event = None

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock
        invoke_cli(
            ctx=ctx_mock,
            function_identifier=self.function_id,
            template=self.template,
            event=self.event,
            no_event=self.no_event,
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
            shutdown=self.shutdown,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_image=self.invoke_image,
        )

        InvokeContextMock.assert_called_with(
            template_file=self.template,
            function_identifier=self.function_id,
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
            shutdown=self.shutdown,
            aws_region=self.region_name,
            aws_profile=self.profile,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_images={None: "amazon/aws-sam-cli-emulation-image-python3.6"},
        )

        get_event_mock.assert_not_called()
        context_mock.local_lambda_runner.invoke.assert_called_with(
            context_mock.function_identifier, event="{}", stdout=context_mock.stdout, stderr=context_mock.stderr
        )

    @parameterized.expand(
        [
            param(FunctionNotFound("not found"), "Function id not found in template"),
            param(DockerImagePullFailedException("Failed to pull image"), "Failed to pull image"),
        ]
    )
    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_must_raise_user_exception_on_function_not_found(
        self, side_effect_exception, expected_exectpion_message, get_event_mock, InvokeContextMock
    ):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock

        context_mock.local_lambda_runner.invoke.side_effect = side_effect_exception

        with self.assertRaises(UserException) as ex_ctx:

            invoke_cli(
                ctx=ctx_mock,
                function_identifier=self.function_id,
                template=self.template,
                event=self.eventfile,
                no_event=self.no_event,
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
                shutdown=self.shutdown,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
                invoke_image=self.invoke_image,
            )

        msg = str(ex_ctx.exception)
        self.assertEqual(msg, expected_exectpion_message)

    @parameterized.expand(
        [
            param(
                InvalidIntermediateImageError("ImageUri not set to a reference-able image for Function: MyFunction"),
                "ImageUri not set to a reference-able image for Function: MyFunction",
            ),
        ]
    )
    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_must_raise_user_exception_on_function_local_invoke_image_not_found_for_IMAGE_packagetype(
        self, side_effect_exception, expected_exectpion_message, get_event_mock, InvokeContextMock
    ):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock

        context_mock.local_lambda_runner.invoke.side_effect = side_effect_exception

        with self.assertRaises(UserException) as ex_ctx:

            invoke_cli(
                ctx=ctx_mock,
                function_identifier=self.function_id,
                template=self.template,
                event=self.eventfile,
                no_event=self.no_event,
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
                shutdown=self.shutdown,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
                invoke_image=self.invoke_image,
            )

        msg = str(ex_ctx.exception)
        self.assertEqual(msg, expected_exectpion_message)

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
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_must_raise_user_exception_on_invalid_sam_template(
        self, exeception_to_raise, execption_message, get_event_mock, InvokeContextMock
    ):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        InvokeContextMock.side_effect = exeception_to_raise

        with self.assertRaises(UserException) as ex_ctx:

            invoke_cli(
                ctx=ctx_mock,
                function_identifier=self.function_id,
                template=self.template,
                event=self.eventfile,
                no_event=self.no_event,
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
                shutdown=self.shutdown,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
                invoke_image=self.invoke_image,
            )

        msg = str(ex_ctx.exception)
        self.assertEqual(msg, execption_message)

    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_must_raise_user_exception_on_invalid_env_vars(self, get_event_mock, InvokeContextMock):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        InvokeContextMock.side_effect = OverridesNotWellDefinedError("bad env vars")

        with self.assertRaises(UserException) as ex_ctx:

            invoke_cli(
                ctx=ctx_mock,
                function_identifier=self.function_id,
                template=self.template,
                event=self.eventfile,
                no_event=self.no_event,
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
                shutdown=self.shutdown,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
                invoke_image=self.invoke_image,
            )

        msg = str(ex_ctx.exception)
        self.assertEqual(msg, "bad env vars")

    @parameterized.expand(
        [
            param(
                ContainerNotStartableException("Container cannot be started, no free ports on host"),
                "Container cannot be started, no free ports on host",
            ),
        ]
    )
    @patch("samcli.commands.local.cli_common.invoke_context.InvokeContext")
    @patch("samcli.commands.local.invoke.cli._get_event")
    def test_must_raise_user_exception_on_function_no_free_ports(
        self, side_effect_exception, expected_exectpion_message, get_event_mock, InvokeContextMock
    ):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock

        context_mock.local_lambda_runner.invoke.side_effect = side_effect_exception

        with self.assertRaises(UserException) as ex_ctx:

            invoke_cli(
                ctx=ctx_mock,
                function_identifier=self.function_id,
                template=self.template,
                event=self.eventfile,
                no_event=self.no_event,
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
                shutdown=self.shutdown,
                container_host=self.container_host,
                container_host_interface=self.container_host_interface,
                invoke_image=self.invoke_image,
            )

        msg = str(ex_ctx.exception)
        self.assertEqual(msg, expected_exectpion_message)


class TestGetEvent(TestCase):
    @parameterized.expand([param(STDIN_FILE_NAME), param("somefile")])
    @patch("samcli.commands.local.invoke.cli.click")
    def test_must_work_with_stdin(self, filename, click_mock):
        event_data = "some data"

        # Mock file pointer
        fp_mock = Mock()

        # Mock the context manager
        click_mock.open_file.return_value.__enter__.return_value = fp_mock
        fp_mock.read.return_value = event_data

        result = invoke_cli_get_event(filename)

        self.assertEqual(result, event_data)
        fp_mock.read.assert_called_with()
