"""
Tests the InvokeContext class
"""

import os
import sys
import yaml
import docker

import requests

from samcli.commands.local.cli_common.user_exceptions import InvokeContextException
from samcli.commands.local.cli_common.invoke_context import InvokeContext

from unittest import TestCase
from mock import Mock, patch, ANY, mock_open
from parameterized import parameterized, param


class TestInvokeContext__enter__(TestCase):

    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_read_from_necessary_files(self, SamFunctionProviderMock):
        function_provider = Mock()

        SamFunctionProviderMock.return_value = function_provider

        template_file = "template_file"
        env_vars_file = "env_vars_file"
        log_file = "log_file"

        invoke_context = InvokeContext(template_file=template_file,
                                       function_identifier="id",
                                       env_vars_file=env_vars_file,
                                       debug_port=123,
                                       debug_args="args",
                                       docker_volume_basedir="volumedir",
                                       docker_network="network",
                                       log_file=log_file,
                                       skip_pull_image=True,
                                       aws_profile="profile")

        template_dict = "template_dict"
        invoke_context._get_template_data = Mock()
        invoke_context._get_template_data.return_value = template_dict

        env_vars_value = "env_vars_value"
        invoke_context._get_env_vars_value = Mock()
        invoke_context._get_env_vars_value.return_value = env_vars_value

        log_file_handle = "handle"
        invoke_context._setup_log_file = Mock()
        invoke_context._setup_log_file.return_value = log_file_handle

        invoke_context._check_docker_connectivity = Mock()

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        self.assertEquals(invoke_context._template_dict, template_dict)
        self.assertEquals(invoke_context._function_provider, function_provider)
        self.assertEquals(invoke_context._env_vars_value, env_vars_value)
        self.assertEquals(invoke_context._log_file_handle, log_file_handle)

        invoke_context._get_template_data.assert_called_with(template_file)
        SamFunctionProviderMock.assert_called_with(template_dict)
        invoke_context._get_env_vars_value.assert_called_with(env_vars_file)
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._check_docker_connectivity.assert_called_with()


class TestInvokeContext__exit__(TestCase):

    def test_must_close_opened_logfile(self):
        context = InvokeContext(template_file="template")
        handle_mock = Mock()
        context._log_file_handle = handle_mock

        context.__exit__()

        handle_mock.close.assert_called_with()
        self.assertIsNone(context._log_file_handle)

    def test_must_ignore_if_handle_is_absent(self):
        context = InvokeContext(template_file="template")
        context._log_file_handle = None

        context.__exit__()
        self.assertIsNone(context._log_file_handle)


class TestInvokeContextAsContextManager(TestCase):
    """
    Must be able to use the class as a context manager
    """

    @patch.object(InvokeContext, "__enter__")
    @patch.object(InvokeContext, "__exit__")
    def test_must_work_in_with_statement(self, ExitMock, EnterMock):

        context_obj = Mock()
        EnterMock.return_value = context_obj

        with InvokeContext(template_file="template_file",
                           function_identifier="id",
                           env_vars_file="env_vars_file",
                           debug_port=123,
                           debug_args="args",
                           docker_volume_basedir="volumedir",
                           docker_network="network",
                           log_file="log_file",
                           skip_pull_image=True,
                           aws_profile="profile") as context:
            self.assertEquals(context_obj, context)

        EnterMock.assert_called_with()
        self.assertEquals(1, ExitMock.call_count)


class TestInvokeContext_function_name_property(TestCase):

    def test_must_return_function_name_if_present(self):
        id = "id"
        context = InvokeContext(template_file="template_file", function_identifier=id)

        self.assertEquals(id, context.function_name)

    def test_must_return_one_function_from_template(self):
        context = InvokeContext(template_file="template_file")

        function = Mock()
        function.name = "myname"
        context._function_provider = Mock()
        context._function_provider.get_all.return_value = [function]  # Provider returns only one function

        self.assertEquals("myname", context.function_name)

    def test_must_raise_if_more_than_one_function(self):
        context = InvokeContext(template_file="template_file")

        context._function_provider = Mock()
        context._function_provider.get_all.return_value = [Mock(), Mock(), Mock()]  # Provider returns three functions

        with self.assertRaises(InvokeContextException):
            context.function_name


class TestInvokeContext_local_lambda_runner(TestCase):

    def setUp(self):
        self.context = InvokeContext(template_file="template_file",
                                     function_identifier="id",
                                     env_vars_file="env_vars_file",
                                     debug_port=123,
                                     debug_args="args",
                                     docker_volume_basedir="volumedir",
                                     docker_network="network",
                                     log_file="log_file",
                                     skip_pull_image=True,
                                     aws_profile="profile")

    @patch("samcli.commands.local.cli_common.invoke_context.ContainerManager")
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    def test_must_create_runner(self, LocalLambdaMock, LambdaRuntimeMock, ContainerManagerMock):

        container_mock = Mock()
        ContainerManagerMock.return_value = container_mock

        runtime_mock = Mock()
        LambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        cwd = "cwd"
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        result = self.context.local_lambda_runner
        self.assertEquals(result, runner_mock)

        ContainerManagerMock.assert_called_with(docker_network_id="network",
                                                skip_pull_image=True)
        LambdaRuntimeMock.assert_called_with(container_mock)
        LocalLambdaMock.assert_called_with(local_runtime=runtime_mock,
                                           function_provider=ANY,
                                           cwd=cwd,
                                           env_vars_values=ANY,
                                           debug_port=123,
                                           debug_args="args",
                                           aws_profile="profile")


class TestInvokeContext_stdout_property(TestCase):

    def test_must_return_log_file_handle(self):
        context = InvokeContext(template_file="template")
        context._log_file_handle = "handle"

        self.assertEquals("handle", context.stdout)

    def test_must_return_sys_stdout(self):
        context = InvokeContext(template_file="template")

        expected_stdout = sys.stdout

        if sys.version_info.major > 2:
            expected_stdout = sys.stdout.buffer

        self.assertEquals(expected_stdout, context.stdout)


class TestInvokeContext_stderr_property(TestCase):

    def test_must_return_log_file_handle(self):
        context = InvokeContext(template_file="template")
        context._log_file_handle = "handle"

        self.assertEquals("handle", context.stderr)

    def test_must_return_sys_stderr(self):
        context = InvokeContext(template_file="template")

        expected_stderr = sys.stderr

        if sys.version_info.major > 2:
            expected_stderr = sys.stderr.buffer

        self.assertEquals(expected_stderr, context.stderr)


class TestInvokeContext_template_property(TestCase):

    def test_must_return_tempalte_dict(self):
        context = InvokeContext(template_file="file")
        context._template_dict = "My template"

        self.assertEquals("My template", context.template)


class TestInvokeContextget_cwd(TestCase):

    def test_must_return_template_file_dir_name(self):
        filename = "filename"
        context = InvokeContext(template_file=filename)

        expected = os.path.dirname(os.path.abspath(filename))
        result = context.get_cwd()

        self.assertEquals(result, expected)

    def test_must_return_docker_volume_dir(self):
        filename = "filename"
        context = InvokeContext(template_file=filename, docker_volume_basedir="basedir")

        result = context.get_cwd()
        self.assertEquals(result, "basedir")


class TestInvokeContext_get_template_data(TestCase):

    def test_must_raise_if_file_does_not_exist(self):
        filename = "filename"

        with self.assertRaises(InvokeContextException) as exception_ctx:
            InvokeContext._get_template_data(filename)

        ex = exception_ctx.exception
        self.assertEquals(str(ex), "Template file not found at {}".format(filename))

    @patch("samcli.commands.local.cli_common.invoke_context.yaml_parse")
    @patch("samcli.commands.local.cli_common.invoke_context.os")
    def test_must_read_file_and_parse(self, os_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"
        parse_result = "parse result"

        os_mock.patch.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.return_value = parse_result

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):
            result = InvokeContext._get_template_data(filename)

            self.assertEquals(result, parse_result)

        m.assert_called_with(filename, 'r')
        yaml_parse_mock.assert_called_with(file_data)

    @parameterized.expand([
        param(ValueError()),
        param(yaml.YAMLError())
    ])
    @patch("samcli.commands.local.cli_common.invoke_context.yaml_parse")
    @patch("samcli.commands.local.cli_common.invoke_context.os")
    def test_must_raise_on_parse_errors(self, exception, os_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"

        os_mock.patch.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.side_effect = exception

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):

            with self.assertRaises(InvokeContextException) as ex_ctx:
                InvokeContext._get_template_data(filename)

            actual_exception = ex_ctx.exception
            self.assertTrue(str(actual_exception).startswith("Failed to parse template: "))


class TestInvokeContext_get_env_vars_value(TestCase):

    def test_must_return_if_no_file(self):
        result = InvokeContext._get_env_vars_value(filename=None)
        self.assertIsNone(result, "No value must be returned")

    def test_must_read_file_and_parse_as_json(self):
        filename = "filename"
        file_data = '{"a": "b"}'
        expected = {"a": "b"}

        m = mock_open(read_data=file_data)

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):
            result = InvokeContext._get_env_vars_value(filename)

            self.assertEquals(expected, result)

        m.assert_called_with(filename, 'r')

    def test_must_raise_if_failed_to_parse_json(self):
        filename = "filename"
        file_data = 'invalid json'

        m = mock_open(read_data=file_data)

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):

            with self.assertRaises(InvokeContextException) as ex_ctx:
                InvokeContext._get_env_vars_value(filename)

            msg = str(ex_ctx.exception)
            self.assertTrue(msg.startswith("Could not read environment variables overrides from file {}".format(
                filename)))


class TestInvokeContext_setup_log_file(TestCase):

    def test_must_return_if_file_not_given(self):
        result = InvokeContext._setup_log_file(log_file=None)
        self.assertIsNone(result, "Log file must not be setup")

    def test_must_open_file_for_writing(self):
        filename = "foo"
        m = mock_open()

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):
            InvokeContext._setup_log_file(filename)

        m.assert_called_with(filename, 'wb')


class TestInvokeContext_check_docker_connectivity(TestCase):

    def test_must_call_ping(self):
        client = Mock()
        InvokeContext._check_docker_connectivity(client)
        client.ping.assert_called_with()

    @patch("samcli.commands.local.cli_common.invoke_context.docker")
    def test_must_call_ping_with_docker_client_from_env(self, docker_mock):
        client = Mock()
        docker_mock.from_env.return_value = client

        InvokeContext._check_docker_connectivity()
        client.ping.assert_called_with()

    @parameterized.expand([
        param("Docker APIError thrown", docker.errors.APIError("error")),
        param("Requests ConnectionError thrown", requests.exceptions.ConnectionError("error"))
    ])
    def test_must_raise_if_docker_not_found(self, test_name, error_docker_throws):
        client = Mock()

        client.ping.side_effect = error_docker_throws

        with self.assertRaises(InvokeContextException) as ex_ctx:
            InvokeContext._check_docker_connectivity(client)

        msg = str(ex_ctx.exception)
        self.assertEquals(msg, "Running AWS SAM projects locally requires Docker. Have you got it installed?")
