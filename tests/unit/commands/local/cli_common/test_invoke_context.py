"""
Tests the InvokeContext class
"""
import errno
import os

from parameterized import parameterized

from samcli.lib.utils.packagetype import ZIP
from samcli.commands._utils.template import TemplateFailedParsingException
from samcli.commands.local.cli_common.invoke_context import (
    InvokeContext,
    ContainersInitializationMode,
    ContainersMode,
    DebugContextException,
    DockerIsNotReachableException,
    NoFunctionIdentifierProvidedException,
    InvalidEnvironmentVariablesFileException,
)

from unittest import TestCase
from unittest.mock import Mock, PropertyMock, patch, ANY, mock_open, call

from samcli.lib.providers.provider import Stack


class TestInvokeContext__enter__(TestCase):
    @patch("samcli.commands.local.cli_common.invoke_context.ContainerManager")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_read_from_necessary_files(self, SamFunctionProviderMock, ContainerManagerMock):
        function_provider = Mock()
        function_provider.get_all.return_value = [
            Mock(
                functionname="name",
                function_id="id",
                handler="app.handler",
                runtime="test",
                packagetype=ZIP,
                inlinecode="| \
                exports.handler = async () => 'Hello World!'",
            )
        ]

        SamFunctionProviderMock.return_value = function_provider

        template_file = "template_file"
        env_vars_file = "env_vars_file"
        log_file = "log_file"

        invoke_context = InvokeContext(
            template_file=template_file,
            function_identifier="id",
            env_vars_file=env_vars_file,
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file=log_file,
            skip_pull_image=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            parameter_overrides={},
            aws_region="region",
            aws_profile="profile",
            shutdown=False,
            invoke_images={None: "image"},
        )

        template_dict = "template_dict"
        stacks = [Stack("", "", template_file, Mock(), template_dict)]
        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = stacks

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
        ContainerManagerMock.return_value = container_manager_mock

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        function_provider.get_all.assert_called_once()
        self.assertEqual(invoke_context._function_provider, function_provider)
        self.assertEqual(invoke_context._env_vars_value, env_vars_value)
        self.assertEqual(invoke_context._log_file_handle, log_file_handle)
        self.assertEqual(invoke_context._debug_context, debug_context_mock)
        self.assertEqual(invoke_context._container_manager, container_manager_mock)
        self.assertEqual(invoke_context._containers_mode, ContainersMode.COLD)
        self.assertEqual(invoke_context._containers_initializing_mode, ContainersInitializationMode.LAZY)
        self.assertEqual(invoke_context._invoke_images, {None: "image"})

        invoke_context._get_stacks.assert_called_once()
        SamFunctionProviderMock.assert_called_with(stacks, True)
        self.assertEqual(invoke_context._global_parameter_overrides, {"AWS::Region": "region"})
        self.assertEqual(invoke_context._get_env_vars_value.call_count, 2)
        self.assertEqual(invoke_context._get_env_vars_value.call_args_list, [call(env_vars_file), call(None)])
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._get_debug_context.assert_called_once_with(
            [1111], "args", "path-to-debugger", "env_vars_value", None
        )
        ContainerManagerMock.assert_called_once_with(
            docker_network_id="network", skip_pull_image=True, do_shutdown_event=False
        )

    @patch("samcli.commands.local.cli_common.invoke_context.ContainerManager")
    @patch("samcli.commands.local.cli_common.invoke_context.RefreshableSamFunctionProvider")
    def test_must_initialize_all_containers_if_warm_containers_is_enabled(
        self, RefreshableSamFunctionProviderMock, ContainerManagerMock
    ):
        function_provider = Mock()
        function = Mock()
        function_provider.get_all.return_value = [function]
        function_provider.functions = {}
        RefreshableSamFunctionProviderMock.return_value = function_provider

        template_file = "template_file"
        env_vars_file = "env_vars_file"
        log_file = "log_file"
        parameter_overrides = {}
        global_parameter_overrides = {"AWS::Region": "region"}

        invoke_context = InvokeContext(
            template_file=template_file,
            function_identifier="id",
            env_vars_file=env_vars_file,
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file=log_file,
            skip_pull_image=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            parameter_overrides=parameter_overrides,
            aws_region="region",
            aws_profile="profile",
            warm_container_initialization_mode=ContainersInitializationMode.EAGER.value,
            shutdown=True,
            invoke_images={None: "image"},
        )

        _initialize_all_functions_containers_mock = Mock()
        invoke_context._initialize_all_functions_containers = _initialize_all_functions_containers_mock

        template_dict = "template_dict"
        stacks = [Stack("", "", template_file, Mock(), template_dict)]
        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = stacks

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
        ContainerManagerMock.return_value = container_manager_mock

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        self.assertEqual(invoke_context._function_provider, function_provider)
        self.assertEqual(invoke_context._env_vars_value, env_vars_value)
        self.assertEqual(invoke_context._log_file_handle, log_file_handle)
        self.assertEqual(invoke_context._debug_context, debug_context_mock)
        self.assertEqual(invoke_context._container_manager, container_manager_mock)
        self.assertEqual(invoke_context._containers_mode, ContainersMode.WARM)
        self.assertEqual(invoke_context._containers_initializing_mode, ContainersInitializationMode.EAGER)
        self.assertEqual(invoke_context._invoke_images, {None: "image"})

        invoke_context._get_stacks.assert_called_once()
        RefreshableSamFunctionProviderMock.assert_called_with(
            stacks, parameter_overrides, global_parameter_overrides, True
        )
        self.assertEqual(invoke_context._global_parameter_overrides, global_parameter_overrides)
        self.assertEqual(invoke_context._get_env_vars_value.call_count, 2)
        self.assertEqual(invoke_context._get_env_vars_value.call_args_list, [call(env_vars_file), call(None)])
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._get_debug_context.assert_called_once_with(
            None, "args", "path-to-debugger", "env_vars_value", None
        )
        ContainerManagerMock.assert_called_once_with(
            docker_network_id="network", skip_pull_image=True, do_shutdown_event=True
        )
        _initialize_all_functions_containers_mock.assert_called_once_with()

    @patch("samcli.commands.local.cli_common.invoke_context.ContainerManager")
    @patch("samcli.commands.local.cli_common.invoke_context.RefreshableSamFunctionProvider")
    def test_must_set_debug_function_if_warm_containers_enabled_no_debug_function_provided_and_template_contains_one_function(
        self, RefreshableSamFunctionProviderMock, ContainerManagerMock
    ):
        function_provider = Mock()
        function = Mock(
            functionname="function_name", handler="app.handler", runtime="test", packagetype=ZIP, inlinecode=None
        )
        function_provider.functions = {"function_name": function}
        function_provider.get_all.return_value = [function]
        RefreshableSamFunctionProviderMock.return_value = function_provider

        template_file = "template_file"
        env_vars_file = "env_vars_file"
        container_env_vars_file = "container_env_vars_file"
        log_file = "log_file"
        parameter_overrides = {}
        global_parameter_overrides = {"AWS::Region": "region"}

        invoke_context = InvokeContext(
            template_file=template_file,
            function_identifier="id",
            env_vars_file=env_vars_file,
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file=log_file,
            skip_pull_image=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            container_env_vars_file=container_env_vars_file,
            debug_args="args",
            parameter_overrides=parameter_overrides,
            aws_region="region",
            aws_profile="profile",
            warm_container_initialization_mode=ContainersInitializationMode.EAGER.value,
            debug_function="",
            shutdown=True,
            invoke_images={None: "image"},
        )

        _initialize_all_functions_containers_mock = Mock()
        invoke_context._initialize_all_functions_containers = _initialize_all_functions_containers_mock

        template_dict = "template_dict"
        stacks = [Stack("", "", template_file, Mock(), template_dict)]
        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = stacks

        invoke_context._get_env_vars_value = Mock(side_effect=["Env var value", "Debug env var value"])

        log_file_handle = "handle"
        invoke_context._setup_log_file = Mock()
        invoke_context._setup_log_file.return_value = log_file_handle

        debug_context_mock = Mock()
        invoke_context._get_debug_context = Mock()
        invoke_context._get_debug_context.return_value = debug_context_mock

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = True
        ContainerManagerMock.return_value = container_manager_mock

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        self.assertEqual(invoke_context._function_provider, function_provider)
        self.assertEqual(invoke_context._env_vars_value, "Env var value")
        self.assertEqual(invoke_context._container_env_vars_value, "Debug env var value")
        self.assertEqual(invoke_context._log_file_handle, log_file_handle)
        self.assertEqual(invoke_context._debug_context, debug_context_mock)
        self.assertEqual(invoke_context._container_manager, container_manager_mock)
        self.assertEqual(invoke_context._containers_mode, ContainersMode.WARM)
        self.assertEqual(invoke_context._containers_initializing_mode, ContainersInitializationMode.EAGER)
        self.assertEqual(invoke_context._invoke_images, {None: "image"})

        invoke_context._get_stacks.assert_called_once()
        RefreshableSamFunctionProviderMock.assert_called_with(
            stacks, parameter_overrides, global_parameter_overrides, True
        )
        self.assertEqual(invoke_context._global_parameter_overrides, global_parameter_overrides)
        self.assertEqual(invoke_context._get_env_vars_value.call_count, 2)
        self.assertEqual(
            invoke_context._get_env_vars_value.call_args_list, [call("env_vars_file"), call("container_env_vars_file")]
        )
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._get_debug_context.assert_called_once_with(
            [1111], "args", "path-to-debugger", "Debug env var value", "function_name"
        )
        ContainerManagerMock.assert_called_once_with(
            docker_network_id="network", skip_pull_image=True, do_shutdown_event=True
        )
        _initialize_all_functions_containers_mock.assert_called_once_with()

    @patch("samcli.commands.local.cli_common.invoke_context.ContainerManager")
    @patch("samcli.commands.local.cli_common.invoke_context.RefreshableSamFunctionProvider")
    def test_no_container_will_be_initialized_if_lazy_containers_is_enabled(
        self, RefreshableSamFunctionProviderMock, ContainerManagerMock
    ):
        function_provider = Mock()
        function_provider.get_all.return_value = [
            Mock(functionname="function_name", handler="app.handler", runtime="test", packagetype=ZIP, inlinecode=None)
        ]

        RefreshableSamFunctionProviderMock.return_value = function_provider

        template_file = "template_file"
        env_vars_file = "env_vars_file"
        log_file = "log_file"
        parameter_overrides = {}
        global_parameter_overrides = {"AWS::Region": "region"}

        invoke_context = InvokeContext(
            template_file=template_file,
            function_identifier="id",
            env_vars_file=env_vars_file,
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file=log_file,
            skip_pull_image=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            parameter_overrides=parameter_overrides,
            aws_region="region",
            aws_profile="profile",
            warm_container_initialization_mode=ContainersInitializationMode.LAZY.value,
            debug_function="debug_function",
            shutdown=True,
            invoke_images={None: "image"},
        )

        template_dict = "template_dict"
        stacks = [Stack("", "", template_file, Mock(), template_dict)]
        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = stacks

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
        ContainerManagerMock.return_value = container_manager_mock

        # Call Enter method manually for testing purposes
        result = invoke_context.__enter__()
        self.assertTrue(result is invoke_context, "__enter__() must return self")

        self.assertEqual(invoke_context._function_provider, function_provider)
        self.assertEqual(invoke_context._env_vars_value, env_vars_value)
        self.assertEqual(invoke_context._log_file_handle, log_file_handle)
        self.assertEqual(invoke_context._debug_context, debug_context_mock)
        self.assertEqual(invoke_context._container_manager, container_manager_mock)
        self.assertEqual(invoke_context._containers_mode, ContainersMode.WARM)
        self.assertEqual(invoke_context._containers_initializing_mode, ContainersInitializationMode.LAZY)
        self.assertEqual(invoke_context._invoke_images, {None: "image"})

        invoke_context._get_stacks.assert_called_once()
        RefreshableSamFunctionProviderMock.assert_called_with(
            stacks, parameter_overrides, global_parameter_overrides, True
        )
        self.assertEqual(invoke_context._global_parameter_overrides, global_parameter_overrides)
        self.assertEqual(invoke_context._get_env_vars_value.call_count, 2)
        self.assertEqual(invoke_context._get_env_vars_value.call_args_list, [call(env_vars_file), call(None)])
        invoke_context._setup_log_file.assert_called_with(log_file)
        invoke_context._get_debug_context.assert_called_once_with(
            [1111], "args", "path-to-debugger", "env_vars_value", "debug_function"
        )
        ContainerManagerMock.assert_called_once_with(
            docker_network_id="network", skip_pull_image=True, do_shutdown_event=True
        )

    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_container_manager_to_check_docker_connectivity(self, SamFunctionProviderMock):
        invoke_context = InvokeContext("template-file")

        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = [Mock()]
        invoke_context._get_env_vars_value = Mock()
        invoke_context._setup_log_file = Mock()
        invoke_context._get_debug_context = Mock()

        container_manager_mock = Mock()

        with patch.object(
            type(container_manager_mock),
            "is_docker_reachable",
            create=True,
            new_callable=PropertyMock,
            return_value=True,
        ) as is_docker_reachable_mock:
            invoke_context._get_container_manager = Mock()
            invoke_context._get_container_manager.return_value = container_manager_mock

            invoke_context.__enter__()

            is_docker_reachable_mock.assert_called_once_with()

    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_raise_if_docker_is_not_reachable(self, SamFunctionProviderMock):
        invoke_context = InvokeContext("template-file")

        invoke_context._get_stacks = Mock()
        invoke_context._get_stacks.return_value = [Mock()]
        invoke_context._get_env_vars_value = Mock()
        invoke_context._setup_log_file = Mock()
        invoke_context._get_debug_context = Mock()

        container_manager_mock = Mock()

        with patch.object(
            type(container_manager_mock),
            "is_docker_reachable",
            create=True,
            new_callable=PropertyMock,
            return_value=False,
        ):

            invoke_context._get_container_manager = Mock()
            invoke_context._get_container_manager.return_value = container_manager_mock

            with self.assertRaises(DockerIsNotReachableException) as ex_ctx:
                invoke_context.__enter__()

                self.assertEqual(
                    "Running AWS SAM projects locally requires Docker. Have you got it installed and running?",
                    str(ex_ctx.exception),
                )

    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider.get_stacks")
    def test_must_raise_if_template_cannot_be_parsed(self, get_buildable_stacks_mock):
        invoke_context = InvokeContext("template-file")

        get_buildable_stacks_mock.side_effect = TemplateFailedParsingException("")
        with self.assertRaises(TemplateFailedParsingException) as ex_ctx:
            invoke_context.__enter__()

    @parameterized.expand(
        [
            (None, "/my/cool/path", True),
            ("LAZY", "/my/cool/path", True),
            (None, None, False),
        ]
    )
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider._extract_functions")
    @patch("samcli.lib.utils.file_observer.SingletonFileObserver.start")
    def test_docker_volume_basedir_set_use_raw_codeuri(
        self, container_mode, docker_volume_basedir, expected, observer_mock, extract_func_mock
    ):
        invoke_context = InvokeContext(
            "template",
            warm_container_initialization_mode=container_mode,
            docker_volume_basedir=docker_volume_basedir,
            shutdown=True,
        )

        invoke_context._initialize_all_functions_containers = Mock()
        invoke_context._get_container_manager = Mock(return_value=Mock())
        invoke_context._get_debug_context = Mock(return_value=Mock())
        invoke_context._get_stacks = Mock(return_value=[])

        invoke_context.__enter__()

        extract_func_mock.assert_called_with([], expected, False, False)


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

        with InvokeContext(
            template_file="template_file",
            function_identifier="id",
            env_vars_file="env_vars_file",
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file="log_file",
            skip_pull_image=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            aws_profile="profile",
            invoke_images={None: "image"},
        ) as context:
            self.assertEqual(context_obj, context)

        EnterMock.assert_called_with()
        self.assertEqual(1, ExitMock.call_count)


class TestInvokeContext_function_name_property(TestCase):
    def test_must_return_function_name_if_present(self):
        id = "id"
        context = InvokeContext(template_file="template_file", function_identifier=id)

        self.assertEqual(id, context.function_identifier)

    def test_must_return_one_function_from_template(self):
        context = InvokeContext(template_file="template_file")

        function = Mock()
        function.name = "myname"
        context._function_provider = Mock()
        context._function_provider.get_all.return_value = [function]  # Provider returns only one function

        self.assertEqual("myname", context.function_identifier)

    def test_must_raise_if_more_than_one_function(self):
        context = InvokeContext(template_file="template_file")

        context._function_provider = Mock()
        context._function_provider.get_all.return_value = [Mock(), Mock(), Mock()]  # Provider returns three functions

        with self.assertRaises(NoFunctionIdentifierProvidedException):
            context.function_identifier


class TestInvokeContext_local_lambda_runner(TestCase):
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaImage")
    @patch("samcli.commands.local.cli_common.invoke_context.LayerDownloader")
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_create_runner(
        self, SamFunctionProviderMock, LocalLambdaMock, LambdaRuntimeMock, download_layers_mock, lambda_image_patch
    ):

        runtime_mock = Mock()
        LambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        download_mock = Mock()
        download_layers_mock.return_value = download_mock

        image_mock = Mock()
        lambda_image_patch.return_value = image_mock

        cwd = "cwd"
        self.context = InvokeContext(
            template_file="template_file",
            function_identifier="id",
            env_vars_file="env_vars_file",
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file="log_file",
            skip_pull_image=True,
            force_image_build=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            aws_profile="profile",
            aws_region="region",
        )
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        self.context._get_stacks = Mock()
        self.context._get_stacks.return_value = [Mock()]
        self.context._get_env_vars_value = Mock()
        self.context._setup_log_file = Mock()
        self.context._get_debug_context = Mock(return_value=None)

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = PropertyMock(return_value=True)
        self.context._get_container_manager = Mock(return_value=container_manager_mock)

        with self.context:
            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)

            LambdaRuntimeMock.assert_called_with(container_manager_mock, image_mock)
            lambda_image_patch.assert_called_once_with(download_mock, True, True, invoke_images=None)
            LocalLambdaMock.assert_called_with(
                local_runtime=runtime_mock,
                function_provider=ANY,
                cwd=cwd,
                debug_context=None,
                env_vars_values=ANY,
                aws_profile="profile",
                aws_region="region",
                container_host=None,
                container_host_interface=None,
            )

            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)
            # assert that lambda runner is created only one time, and the cached version used in the second call
            self.assertEqual(LocalLambdaMock.call_count, 1)

    @patch("samcli.commands.local.cli_common.invoke_context.LambdaImage")
    @patch("samcli.commands.local.cli_common.invoke_context.LayerDownloader")
    @patch("samcli.commands.local.cli_common.invoke_context.WarmLambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    @patch("samcli.commands.local.cli_common.invoke_context.RefreshableSamFunctionProvider")
    def test_must_create_runner_using_warm_containers(
        self,
        RefreshableSamFunctionProviderMock,
        LocalLambdaMock,
        WarmLambdaRuntimeMock,
        download_layers_mock,
        lambda_image_patch,
    ):
        runtime_mock = Mock()
        WarmLambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        download_mock = Mock()
        download_layers_mock.return_value = download_mock

        image_mock = Mock()
        lambda_image_patch.return_value = image_mock

        cwd = "cwd"
        self.context = InvokeContext(
            template_file="template_file",
            function_identifier="id",
            env_vars_file="env_vars_file",
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file="log_file",
            skip_pull_image=True,
            force_image_build=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            aws_profile="profile",
            aws_region="region",
            warm_container_initialization_mode=ContainersInitializationMode.EAGER,
        )
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        self.context._get_stacks = Mock()
        self.context._get_stacks.return_value = [Mock()]
        self.context._get_env_vars_value = Mock()
        self.context._setup_log_file = Mock()
        self.context._get_debug_context = Mock(return_value=None)

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = PropertyMock(return_value=True)
        self.context._get_container_manager = Mock(return_value=container_manager_mock)

        with self.context:
            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)

            WarmLambdaRuntimeMock.assert_called_with(container_manager_mock, image_mock)
            lambda_image_patch.assert_called_once_with(download_mock, True, True, invoke_images=None)
            LocalLambdaMock.assert_called_with(
                local_runtime=runtime_mock,
                function_provider=ANY,
                cwd=cwd,
                debug_context=None,
                env_vars_values=ANY,
                aws_profile="profile",
                aws_region="region",
                container_host=None,
                container_host_interface=None,
            )

            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)
            # assert that lambda runner is created only one time, and the cached version used in the second call
            self.assertEqual(LocalLambdaMock.call_count, 1)

    @patch("samcli.commands.local.cli_common.invoke_context.LambdaImage")
    @patch("samcli.commands.local.cli_common.invoke_context.LayerDownloader")
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_create_runner_with_container_host_option(
        self, SamFunctionProviderMock, LocalLambdaMock, LambdaRuntimeMock, download_layers_mock, lambda_image_patch
    ):
        runtime_mock = Mock()
        LambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        download_mock = Mock()
        download_layers_mock.return_value = download_mock

        image_mock = Mock()
        lambda_image_patch.return_value = image_mock

        cwd = "cwd"
        self.context = InvokeContext(
            template_file="template_file",
            function_identifier="id",
            env_vars_file="env_vars_file",
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file="log_file",
            skip_pull_image=True,
            force_image_build=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            aws_profile="profile",
            aws_region="region",
            container_host="abcdef",
            container_host_interface="192.168.100.101",
        )
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        self.context._get_stacks = Mock()
        self.context._get_stacks.return_value = [Mock()]
        self.context._get_env_vars_value = Mock()
        self.context._setup_log_file = Mock()
        self.context._get_debug_context = Mock(return_value=None)

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = PropertyMock(return_value=True)
        self.context._get_container_manager = Mock(return_value=container_manager_mock)

        with self.context:
            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)

            LambdaRuntimeMock.assert_called_with(container_manager_mock, image_mock)
            lambda_image_patch.assert_called_once_with(download_mock, True, True, invoke_images=None)
            LocalLambdaMock.assert_called_with(
                local_runtime=runtime_mock,
                function_provider=ANY,
                cwd=cwd,
                debug_context=None,
                env_vars_values=ANY,
                aws_profile="profile",
                aws_region="region",
                container_host="abcdef",
                container_host_interface="192.168.100.101",
            )

            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)
            # assert that lambda runner is created only one time, and the cached version used in the second call
            self.assertEqual(LocalLambdaMock.call_count, 1)

    @patch("samcli.commands.local.cli_common.invoke_context.LambdaImage")
    @patch("samcli.commands.local.cli_common.invoke_context.LayerDownloader")
    @patch("samcli.commands.local.cli_common.invoke_context.LambdaRuntime")
    @patch("samcli.commands.local.cli_common.invoke_context.LocalLambdaRunner")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_create_runner_with_invoke_image_option(
        self, SamFunctionProviderMock, LocalLambdaMock, LambdaRuntimeMock, download_layers_mock, lambda_image_patch
    ):

        runtime_mock = Mock()
        LambdaRuntimeMock.return_value = runtime_mock

        runner_mock = Mock()
        LocalLambdaMock.return_value = runner_mock

        download_mock = Mock()
        download_layers_mock.return_value = download_mock

        image_mock = Mock()
        lambda_image_patch.return_value = image_mock

        cwd = "cwd"
        self.context = InvokeContext(
            template_file="template_file",
            function_identifier="id",
            env_vars_file="env_vars_file",
            docker_volume_basedir="volumedir",
            docker_network="network",
            log_file="log_file",
            skip_pull_image=True,
            force_image_build=True,
            debug_ports=[1111],
            debugger_path="path-to-debugger",
            debug_args="args",
            aws_profile="profile",
            aws_region="region",
            invoke_images={None: "image"},
        )
        self.context.get_cwd = Mock()
        self.context.get_cwd.return_value = cwd

        self.context._get_stacks = Mock()
        self.context._get_stacks.return_value = [Mock()]
        self.context._get_env_vars_value = Mock()
        self.context._setup_log_file = Mock()
        self.context._get_debug_context = Mock(return_value=None)

        container_manager_mock = Mock()
        container_manager_mock.is_docker_reachable = PropertyMock(return_value=True)
        self.context._get_container_manager = Mock(return_value=container_manager_mock)

        with self.context:
            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)

            LambdaRuntimeMock.assert_called_with(container_manager_mock, image_mock)
            lambda_image_patch.assert_called_once_with(download_mock, True, True, invoke_images={None: "image"})
            LocalLambdaMock.assert_called_with(
                local_runtime=runtime_mock,
                function_provider=ANY,
                cwd=cwd,
                debug_context=None,
                env_vars_values=ANY,
                aws_profile="profile",
                aws_region="region",
                container_host=None,
                container_host_interface=None,
            )

            result = self.context.local_lambda_runner
            self.assertEqual(result, runner_mock)
            # assert that lambda runner is created only one time, and the cached version used in the second call
            self.assertEqual(LocalLambdaMock.call_count, 1)


class TestInvokeContext_stdout_property(TestCase):
    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.osutils.stdout")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_enable_auto_flush(self, SamFunctionProviderMock, StreamWriterMock, osutils_stdout_mock, ExitMock):
        context = InvokeContext(template_file="template")

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()
        context._setup_log_file = Mock()

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                context.stdout

        StreamWriterMock.assert_called_once_with(ANY, auto_flush=True)

    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.osutils.stdout")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_stdout_if_no_log_file_handle(
        self, SamFunctionProviderMock, StreamWriterMock, osutils_stdout_mock, ExitMock
    ):
        stream_writer_mock = Mock()
        StreamWriterMock.return_value = stream_writer_mock

        stdout_mock = Mock()
        osutils_stdout_mock.return_value = stdout_mock

        context = InvokeContext(template_file="template")

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()
        context._setup_log_file = Mock(return_value=None)

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                stdout = context.stdout

                StreamWriterMock.assert_called_once_with(stdout_mock, ANY)
                self.assertEqual(stream_writer_mock, stdout)

    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_log_file_handle(self, SamFunctionProviderMock, StreamWriterMock, ExitMock):

        stream_writer_mock = Mock()
        StreamWriterMock.return_value = stream_writer_mock

        context = InvokeContext(template_file="template")

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()

        log_file_handle_mock = Mock()
        context._setup_log_file = Mock(return_value=log_file_handle_mock)

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                stdout = context.stdout

                StreamWriterMock.assert_called_once_with(log_file_handle_mock, ANY)
                self.assertEqual(stream_writer_mock, stdout)


class TestInvokeContext_stderr_property(TestCase):
    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.osutils.stderr")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_enable_auto_flush(self, SamFunctionProviderMock, StreamWriterMock, osutils_stderr_mock, ExitMock):

        context = InvokeContext(template_file="template", debug_ports=[6000])

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()
        context._setup_log_file = Mock()

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                context.stderr

        StreamWriterMock.assert_called_once_with(ANY, auto_flush=True)

    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.osutils.stderr")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_stderr_if_no_log_file_handle(
        self, SamFunctionProviderMock, StreamWriterMock, osutils_stderr_mock, ExitMock
    ):

        stream_writer_mock = Mock()
        StreamWriterMock.return_value = stream_writer_mock

        stderr_mock = Mock()
        osutils_stderr_mock.return_value = stderr_mock

        context = InvokeContext(template_file="template")

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()
        context._setup_log_file = Mock(return_value=None)

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                stderr = context.stderr

                StreamWriterMock.assert_called_once_with(stderr_mock, ANY)
                self.assertEqual(stream_writer_mock, stderr)

    @patch.object(InvokeContext, "__exit__")
    @patch("samcli.commands.local.cli_common.invoke_context.StreamWriter")
    @patch("samcli.commands.local.cli_common.invoke_context.SamFunctionProvider")
    def test_must_use_log_file_handle(self, SamFunctionProviderMock, StreamWriterMock, ExitMock):

        stream_writer_mock = Mock()
        StreamWriterMock.return_value = stream_writer_mock

        context = InvokeContext(template_file="template")

        context._get_stacks = Mock()
        context._get_stacks.return_value = [Mock()]
        context._get_env_vars_value = Mock()

        log_file_handle_mock = Mock()
        context._setup_log_file = Mock(return_value=log_file_handle_mock)

        container_manager_mock = Mock()
        context._get_container_manager = Mock(return_value=container_manager_mock)

        with patch.object(type(container_manager_mock), "is_docker_reachable", create=True, return_value=True):
            with context:
                stderr = context.stderr

                StreamWriterMock.assert_called_once_with(log_file_handle_mock, ANY)
                self.assertEqual(stream_writer_mock, stderr)


class TestInvokeContextget_cwd(TestCase):
    def test_must_return_template_file_dir_name(self):
        filename = "filename"
        context = InvokeContext(template_file=filename)

        expected = os.path.dirname(os.path.abspath(filename))
        result = context.get_cwd()

        self.assertEqual(result, expected)

    def test_must_return_docker_volume_dir(self):
        filename = "filename"
        context = InvokeContext(template_file=filename, docker_volume_basedir="basedir")

        result = context.get_cwd()
        self.assertEqual(result, "basedir")


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

            self.assertEqual(expected, result)

        m.assert_called_with(filename, "r")

    def test_must_raise_if_failed_to_parse_json(self):
        filename = "filename"
        file_data = "invalid json"

        m = mock_open(read_data=file_data)

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):

            with self.assertRaises(InvalidEnvironmentVariablesFileException) as ex_ctx:
                InvokeContext._get_env_vars_value(filename)

            msg = str(ex_ctx.exception)
            self.assertTrue(
                msg.startswith("Could not read environment variables overrides from file {}".format(filename))
            )


class TestInvokeContext_setup_log_file(TestCase):
    def test_must_return_if_file_not_given(self):
        result = InvokeContext._setup_log_file(log_file=None)
        self.assertIsNone(result, "Log file must not be setup")

    def test_must_open_file_for_writing(self):
        filename = "foo"
        m = mock_open()

        with patch("samcli.commands.local.cli_common.invoke_context.open", m):
            InvokeContext._setup_log_file(filename)

        m.assert_called_with(filename, "wb")


class TestInvokeContext_get_debug_context(TestCase):
    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debugger_path_not_found(self, pathlib_mock):
        error = OSError()
        error.errno = errno.ENOENT
        pathlib_mock.side_effect = error

        with self.assertRaises(DebugContextException):
            InvokeContext._get_debug_context(
                debug_ports=[1111], debug_args=None, debugger_path="somepath", container_env_vars=None
            )

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debugger_path_not_dir(self, pathlib_mock):
        pathlib_path_mock = Mock()
        resolve_path_mock = Mock()
        pathlib_path_mock.resolve.return_value = resolve_path_mock
        resolve_path_mock.is_dir.return_value = False
        pathlib_mock.return_value = pathlib_path_mock

        with self.assertRaises(DebugContextException):
            InvokeContext._get_debug_context(
                debug_ports=1111, debug_args=None, debugger_path="somepath", container_env_vars=None
            )

    def test_no_debug_port(self):
        debug_context = InvokeContext._get_debug_context(None, None, None, {})

        self.assertEqual(debug_context.debugger_path, None)
        self.assertEqual(debug_context.debug_ports, None)
        self.assertEqual(debug_context.debug_args, None)
        self.assertEqual(debug_context.container_env_vars, {})

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_non_path_not_found_oserror_is_thrown(self, pathlib_mock):
        pathlib_mock.side_effect = OSError()

        with self.assertRaises(OSError):
            InvokeContext._get_debug_context(
                debug_ports=1111, debug_args=None, debugger_path="somepath", container_env_vars=None
            )

    @patch("samcli.commands.local.cli_common.invoke_context.DebugContext")
    def test_debug_port_given_without_debugger_path(self, debug_context_mock):
        debug_context_mock.return_value = "I am the DebugContext"
        debug_context = InvokeContext._get_debug_context(
            debug_ports=1111, debug_args=None, debugger_path=None, container_env_vars={"env": "var"}
        )

        self.assertEqual(debug_context, "I am the DebugContext")
        debug_context_mock.assert_called_once_with(
            debug_ports=1111,
            debug_args=None,
            debugger_path=None,
            debug_function=None,
            container_env_vars={"env": "var"},
        )

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debug_port_not_specified(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports=None, debug_args=None, debugger_path="somepath", container_env_vars=None
        )
        self.assertEqual(None, debug_context.debug_ports)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_container_env_vars_specified(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports=1111, debug_args=None, debugger_path="somepath", container_env_vars={"env": "var"}
        )
        self.assertEqual({"env": "var"}, debug_context.container_env_vars)
        self.assertEqual(1111, debug_context.debug_ports)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debug_port_single_value_int(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports=1111, debug_args=None, debugger_path="somepath", container_env_vars={}
        )
        self.assertEqual(1111, debug_context.debug_ports)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debug_port_single_value_string(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports="1111", debug_args=None, debugger_path="somepath", container_env_vars=None
        )
        self.assertEqual("1111", debug_context.debug_ports)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debug_port_multiple_values_string(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports=["1111", "1112"], debug_args=None, debugger_path="somepath", container_env_vars=None
        )
        self.assertEqual(["1111", "1112"], debug_context.debug_ports)

    @patch("samcli.commands.local.cli_common.invoke_context.Path")
    def test_debug_port_multiple_values_int(self, pathlib_mock):
        pathlib_path_mock = Mock()
        pathlib_mock.return_value = pathlib_path_mock

        debug_context = InvokeContext._get_debug_context(
            debug_ports=[1111, 1112], debug_args=None, debugger_path="somepath", container_env_vars=None
        )
        self.assertEqual([1111, 1112], debug_context.debug_ports)

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

        debug_context = InvokeContext._get_debug_context(1111, "args", "./path", None)

        self.assertEqual(debug_context, "I am the DebugContext")

        debug_context_mock.assert_called_once_with(
            debug_ports=1111, debug_args="args", debugger_path="full/path", debug_function=None, container_env_vars=None
        )
        resolve_path_mock.is_dir.assert_called_once()
        pathlib_path_mock.resolve.assert_called_once_with(strict=True)
        pathlib_mock.assert_called_once_with("./path")


class TestInvokeContext_get_stacks(TestCase):
    @patch("samcli.commands.local.cli_common.invoke_context.SamLocalStackProvider.get_stacks")
    def test_must_pass_custom_region(self, get_stacks_mock):
        get_stacks_mock.return_value = [Mock(), []]
        invoke_context = InvokeContext("template_file", aws_region="my-custom-region")
        invoke_context._get_stacks()
        get_stacks_mock.assert_called_with(
            "template_file", parameter_overrides=None, global_parameter_overrides={"AWS::Region": "my-custom-region"}
        )
