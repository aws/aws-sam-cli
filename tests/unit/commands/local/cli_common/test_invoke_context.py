"""
Tests the InvokeContext class
"""
import errno
import os
import sys

from samcli.commands.local.cli_common.user_exceptions import InvokeContextException, DebugContextException
from samcli.commands.local.cli_common.invoke_context import InvokeContext

from unittest import TestCase
from mock import Mock, PropertyMock, patch, ANY, mock_open


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
                                       docker_volume_basedir="volumedir",
                                       docker_network="network",
                                       log_file=log_file,
                                       skip_pull_image=True,
                                       debug_port=1111,
                                       debugger_path="path-to-debugger",
                                       debug_args='args',
                                       parameter_overrides={},
                                       aws_region="region")

        template_dict = "template_dict"
        invoke_context._get_template_data = Mock()
        invoke_context._get_template_data.return_value = template_dict

        env_vars_value = "env_vars_value"
        invoke_context._get_env_vars_value = Mock()
        invoke_context._get_env_vars_value.return_value = env_vars_value

        log_file_handle = "handle"
        invoke_context._setup_log_file = Mock()
        invoke_context._setup_log_file.return_value = log_file_handle

        debug_context_mock = Mock()
        invoke_context._get_debug_context = Mock()
        invoke_context._get_debug_context.return_value = debug_context_mock

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = True
        invoke_context._get_container_manager = Mock(return_value=container_manager_mock)

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        self.assertEqual(invoke_context._template_dict, template_dict)
        self.assertEqual(invoke_context._function_provider, function_provider)
        self.assertEqual(invoke_context._env_vars_value, env_vars_value)
        self.assertEqual(invoke_context._log_file_handle, log_file_handle)
        self.assertEqual(invoke_context._debug_context, debug_context_mock)
        self.assertEqual(invoke_context._container_manager, container_manager_mock)

        invoke_context._get_template_data.assert_called_with(template_file)
        SamFunctionProviderMock.assert_called_with(template_dict, {"AWS::Region": "region"})
        invoke_context._get_env_vars_value.assert_called_with(env_vars_file)
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._get_debug_context.assert_called_once_with(1111, "args", "path-to-debugger")
        invoke_context._get_container_manager.assert_called_once_with("network", True)

    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_container_manager_to_check_docker_connectivity(self, SamFunctionProviderMock):
        invoke_context = InvokeContext("template-file")

        invoke_context._get_template_data = Mock()
        invoke_context._get_env_vars_value = Mock()
        invoke_context._setup_log_file = Mock()
        invoke_context._get_debug_context = Mock()

        container_manager_mock = Mock()

        with patch.object(type(container_manager_mock), "is_docker_reachable",
                          create=True, new_callable=PropertyMock, return_value=True) as is_docker_reachable_mock:
            invoke_context._get_container_manager = Mock()
            invoke_context._get_container_manager.return_value = container_manager_mock

            invoke_context.__enter__()

            is_docker_reachable_mock.assert_called_once_with()

    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_raise_if_docker_is_not_reachable(self, SamFunctionProviderMock):
        invoke_context = InvokeContext("template-file")

        invoke_context._get_template_data = Mock()
        invoke_context._get_env_vars_value = Mock()
        invoke_context._setup_log_file = Mock()
        invoke_context._get_debug_context = Mock()

        container_manager_mock = Mock()

        with patch.object(type(container_manager_mock), "is_docker_reachable",
                          create=True, new_callable=PropertyMock, return_value=False):

            invoke_context._get_container_manager = Mock()
            invoke_context._get_container_manager.return_value = container_manager_mock

            with self.assertRaises(InvokeContextException) as ex_ctx:
                invoke_context.__enter__()

                self.assertEqual("Running AWS SAM projects locally requires Docker. Have you got it installed?",
                                 str(ex_ctx.exception))


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
                           docker_volume_basedir="volumedir",
                           docker_network="network",
                           log_file="log_file",
                           skip_pull_image=True,
                           debug_port=1111,
                           debugger_path="path-to-debugger",
                           debug_args='args') as context:
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
                                     docker_volume_basedir="volumedir",
                                     docker_network="network",
                                     log_file="log_file",
                                     skip_pull_image=True,
                                     force_image_build=True,
                                     debug_port=1111,
                                     debugger_path="path-to-debugger",
                                     debug_args='args')

    @patch("samcli.commands.local.cli_common.invoke_context.LambdaImage")
    @patch("samcli.commands.local.cli_common.invoke_context.LayerDownloader")
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_create_runner(self,
                                SamFunctionProviderMock,
                                LocalLambdaMock,
                                LambdaRuntimeMock,
                                download_layers_mock,
                                lambda_image_patch):

        runtime_mock = Mock()
        LambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        download_mock = Mock()
        download_layers_mock.return_value = download_mock

        image_mock = Mock()
        lambda_image_patch.return_value = image_mock

        cwd = "cwd"
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        self.context._get_template_data = Mock()
        self.context._get_env_vars_value = Mock()
        self.context._setup_log_file = Mock()
        self.context._get_debug_context = Mock(return_value=None)

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = PropertyMock(return_value=True)
        self.context._get_container_manager = Mock(return_value=container_manager_mock)

        with self.context:
            result = self.context.local_lambda_runner
            self.assertEquals(result, runner_mock)

            LambdaRuntimeMock.assert_called_with(container_manager_mock, image_mock)
            lambda_image_patch.assert_called_once_with(download_mock, True, True)
            LocalLambdaMock.assert_called_with(local_runtime=runtime_mock,
                                               function_provider=ANY,
                                               cwd=cwd,
                                               debug_context=None,
                                               env_vars_values=ANY)


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


class TestInvokeContext_get_debug_context(TestCase):

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debugger_path_not_found(self, pathlib_mock):
        error = OSError()
        error.errno = errno.ENOENT
        pathlib_mock.side_effect = error

        with self.assertRaises(DebugContextException):
            InvokeContext._get_debug_context(debug_port=1111, debug_args=None, debugger_path='somepath')

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debugger_path_not_dir(self, pathlib_mock):
        pathlib_path_mock = Mock()
        resolve_path_mock = Mock()
        pathlib_path_mock.resolve.return_value = resolve_path_mock
        resolve_path_mock.is_dir.return_value = False
        pathlib_mock.return_value = pathlib_path_mock

        with self.assertRaises(DebugContextException):
            InvokeContext._get_debug_context(debug_port=1111, debug_args=None, debugger_path='somepath')

    def test_no_debug_port(self):
        debug_context = InvokeContext._get_debug_context(None, None, None)

        self.assertEquals(debug_context.debugger_path, None)
        self.assertEquals(debug_context.debug_port, None)
        self.assertEquals(debug_context.debug_args, None)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_non_path_not_found_oserror_is_thrown(self, pathlib_mock):
        pathlib_mock.side_effect = OSError()

        with self.assertRaises(OSError):
            InvokeContext._get_debug_context(debug_port=1111, debug_args=None, debugger_path='somepath')

    @patch("samcli.commands.local.cli_common.invoke_context.DebugContext")
    def test_debug_port_given_without_debugger_path(self, debug_context_mock):
        debug_context_mock.return_value = "I am the DebugContext"

        debug_context = InvokeContext._get_debug_context(1111, None, None)

        self.assertEquals(debug_context, "I am the DebugContext")

        debug_context_mock.assert_called_once_with(debug_port=1111, debug_args=None, debugger_path=None)

    @patch("samcli.commands.local.cli_common.invoke_context.DebugContext")
    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debugger_path_resolves(self, pathlib_mock, debug_context_mock):
        pathlib_path_mock = Mock()
        resolve_path_mock = Mock()
        pathlib_path_mock.resolve.return_value = resolve_path_mock
        resolve_path_mock.is_dir.return_value = True
        resolve_path_mock.__str__ = Mock()
        resolve_path_mock.__str__.return_value = "full/path"
        pathlib_mock.return_value = pathlib_path_mock

        debug_context_mock.return_value = "I am the DebugContext"

        debug_context = InvokeContext._get_debug_context(1111, "args", "./path")

        self.assertEquals(debug_context, "I am the DebugContext")

        debug_context_mock.assert_called_once_with(debug_port=1111, debug_args="args", debugger_path="full/path")
        resolve_path_mock.is_dir.assert_called_once()
        pathlib_path_mock.resolve.assert_called_once_with(strict=True)
        pathlib_mock.assert_called_once_with("./path")
