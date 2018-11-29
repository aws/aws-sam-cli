from unittest import TestCase
from mock import patch, Mock

from parameterized import parameterized

from samcli.commands.local.start_lambda.cli import do_cli as start_lambda_cli
from samcli.commands.local.lib.exceptions import InvalidLayerReference
from samcli.commands.local.cli_common.user_exceptions import UserException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
from samcli.local.docker.lambda_container import DebuggingNotSupported


class TestCli(TestCase):

    def setUp(self):
        self.template = "template"
        self.env_vars = "env-vars"
        self.debug_port = 123
        self.debug_args = "args"
        self.debugger_path = "/test/path"
        self.docker_volume_basedir = "basedir"
        self.docker_network = "network"
        self.log_file = "logfile"
        self.skip_pull_image = True
        self.parameter_overrides = {}
        self.layer_cache_basedir = "/some/layers/path"
        self.force_image_build = True
        self.region_name = "region"

        self.ctx_mock = Mock()
        self.ctx_mock.region = self.region_name

        self.host = "host"
        self.port = 123

    @patch("samcli.commands.local.start_lambda.cli.InvokeContext")
    @patch("samcli.commands.local.start_lambda.cli.LocalLambdaService")
    def test_cli_must_setup_context_and_start_service(self, local_lambda_service_mock,
                                                      invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        service_mock = Mock()
        local_lambda_service_mock.return_value = service_mock

        self.call_cli()

        invoke_context_mock.assert_called_with(template_file=self.template,
                                               function_identifier=None,
                                               env_vars_file=self.env_vars,
                                               docker_volume_basedir=self.docker_volume_basedir,
                                               docker_network=self.docker_network,
                                               log_file=self.log_file,
                                               skip_pull_image=self.skip_pull_image,
                                               debug_port=self.debug_port,
                                               debug_args=self.debug_args,
                                               debugger_path=self.debugger_path,
                                               parameter_overrides=self.parameter_overrides,
                                               layer_cache_basedir=self.layer_cache_basedir,
                                               force_image_build=self.force_image_build,
                                               aws_region=self.region_name)

        local_lambda_service_mock.assert_called_with(lambda_invoke_context=context_mock,
                                                     port=self.port,
                                                     host=self.host)

        service_mock.start.assert_called_with()

    @parameterized.expand([(InvalidSamDocumentException("bad template"), "bad template"),
                           (InvalidLayerReference(), "Layer References need to be of type "
                                                     "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'"),
                           (DebuggingNotSupported("Debugging not supported"), "Debugging not supported")
                           ])
    @patch("samcli.commands.local.start_lambda.cli.InvokeContext")
    def test_must_raise_user_exception_on_invalid_sam_template(self,
                                                               exeception_to_raise,
                                                               execption_message,
                                                               invoke_context_mock
                                                               ):
        invoke_context_mock.side_effect = exeception_to_raise

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = execption_message
        self.assertEquals(msg, expected)

    @patch("samcli.commands.local.start_lambda.cli.InvokeContext")
    def test_must_raise_user_exception_on_invalid_env_vars(self, invoke_context_mock):
        invoke_context_mock.side_effect = OverridesNotWellDefinedError("bad env vars")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "bad env vars"
        self.assertEquals(msg, expected)

    def call_cli(self):
        start_lambda_cli(ctx=self.ctx_mock,
                         host=self.host,
                         port=self.port,
                         template=self.template,
                         env_vars=self.env_vars,
                         debug_port=self.debug_port,
                         debug_args=self.debug_args,
                         debugger_path=self.debugger_path,
                         docker_volume_basedir=self.docker_volume_basedir,
                         docker_network=self.docker_network,
                         log_file=self.log_file,
                         skip_pull_image=self.skip_pull_image,
                         parameter_overrides=self.parameter_overrides,
                         layer_cache_basedir=self.layer_cache_basedir,
                         force_image_build=self.force_image_build)
