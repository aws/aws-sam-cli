"""
Unit test for `start-api` CLI
"""

from unittest import TestCase
from mock import patch, Mock

from samcli.commands.local.start_api.cli import do_cli as start_api_cli
from samcli.commands.local.lib.exceptions import NoApisDefined
from samcli.commands.exceptions import UserException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError


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
        self.profile = "profile"
        self.region = "region"
        self.parameter_overrides = {}

        self.host = "host"
        self.port = 123
        self.static_dir = "staticdir"

    @patch("samcli.commands.local.start_api.cli.InvokeContext")
    @patch("samcli.commands.local.start_api.cli.LocalApiService")
    def test_cli_must_setup_context_and_start_service(self, local_api_service_mock,
                                                      invoke_context_mock):
        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        service_mock = Mock()
        local_api_service_mock.return_value = service_mock

        self.call_cli()

        invoke_context_mock.assert_called_with(template_file=self.template,
                                               function_identifier=None,
                                               env_vars_file=self.env_vars,
                                               docker_volume_basedir=self.docker_volume_basedir,
                                               docker_network=self.docker_network,
                                               log_file=self.log_file,
                                               skip_pull_image=self.skip_pull_image,
                                               aws_profile=self.profile,
                                               debug_port=self.debug_port,
                                               debug_args=self.debug_args,
                                               debugger_path=self.debugger_path,
                                               aws_region=self.region,
                                               parameter_overrides=self.parameter_overrides)

        local_api_service_mock.assert_called_with(lambda_invoke_context=context_mock,
                                                  port=self.port,
                                                  host=self.host,
                                                  static_dir=self.static_dir)

        service_mock.start.assert_called_with()

    @patch("samcli.commands.local.start_api.cli.InvokeContext")
    @patch("samcli.commands.local.start_api.cli.LocalApiService")
    def test_must_raise_if_no_api_defined(self, local_api_service_mock, invoke_context_mock):

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        invoke_context_mock.return_value.__enter__.return_value = context_mock

        service_mock = Mock()
        local_api_service_mock.return_value = service_mock
        service_mock.start.side_effect = NoApisDefined("no apis")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "Template does not have any APIs connected to Lambda functions"
        self.assertEquals(msg, expected)

    @patch("samcli.commands.local.start_api.cli.InvokeContext")
    def test_must_raise_user_exception_on_invalid_sam_template(self, invoke_context_mock):

        invoke_context_mock.side_effect = InvalidSamDocumentException("bad template")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "bad template"
        self.assertEquals(msg, expected)

    @patch("samcli.commands.local.start_api.cli.InvokeContext")
    def test_must_raise_user_exception_on_invalid_env_vars(self, invoke_context_mock):
        invoke_context_mock.side_effect = OverridesNotWellDefinedError("bad env vars")

        with self.assertRaises(UserException) as context:
            self.call_cli()

        msg = str(context.exception)
        expected = "bad env vars"
        self.assertEquals(msg, expected)

    def call_cli(self):
        start_api_cli(ctx=None,
                      host=self.host,
                      port=self.port,
                      static_dir=self.static_dir,
                      template=self.template,
                      env_vars=self.env_vars,
                      debug_port=self.debug_port,
                      debug_args=self.debug_args,
                      debugger_path=self.debugger_path,
                      docker_volume_basedir=self.docker_volume_basedir,
                      docker_network=self.docker_network,
                      log_file=self.log_file,
                      skip_pull_image=self.skip_pull_image,
                      profile=self.profile,
                      region=self.region,
                      parameter_overrides=self.parameter_overrides)
