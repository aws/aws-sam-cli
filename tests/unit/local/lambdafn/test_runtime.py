"""
Unit tests for Lambda runtime
"""

from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, ANY, call
from parameterized import parameterized

from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.providers.provider import LayerVersion
from samcli.local.lambdafn.env_vars import EnvironmentVariables
from samcli.local.lambdafn.runtime import LambdaRuntime, _unzip_file, WarmLambdaRuntime, _require_container_reloading
from samcli.local.lambdafn.config import FunctionConfig
from samcli.local.docker.container import ContainerContext


class LambdaRuntime_create(TestCase):
    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.manager_mock = Mock()
        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.layers = []
        self.manager_mock = Mock()
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "x86_64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LOG")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_create_lambda_container(self, LambdaContainerMock, LogMock):
        code_dir = "some code dir"

        container = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container

        self.runtime.create(self.func_config, debug_context=debug_options)

        LogMock.assert_not_called()

        # Make sure env-vars get resolved
        self.env_vars.resolve.assert_called_with()

        # Make sure the context manager is called to return the code directory
        self.runtime._get_code_dir.assert_called_with(self.code_path)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )
        # Run the container and get results
        self.manager_mock.create.assert_called_with(container, ContainerContext.INVOKE)

    @patch("samcli.local.lambdafn.runtime.LOG")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_create_lambda_container_without_mem_limit(self, LambdaContainerMock, LogMock):
        code_dir = "some code dir"

        container = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock, no_mem_limit=True)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container

        self.runtime.create(self.func_config, debug_context=debug_options)

        LogMock.assert_not_called()

        # Make sure env-vars get resolved
        self.env_vars.resolve.assert_called_with()

        # Make sure the context manager is called to return the code directory
        self.runtime._get_code_dir.assert_called_with(self.code_path)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=None,  # No memory limit
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )
        # Run the container and get results
        self.manager_mock.create.assert_called_with(container, ContainerContext.INVOKE)

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_keyboard_interrupt_must_raise(self, LambdaContainerMock):
        code_dir = "some code dir"

        container = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container

        self.manager_mock.create.side_effect = KeyboardInterrupt("some exception")

        with self.assertRaises(KeyboardInterrupt):
            self.runtime.create(self.func_config, debug_context=debug_options)

    @patch("samcli.local.lambdafn.runtime.LOG")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_log_if_template_has_runtime_version(self, LambdaContainerMock, LogMock):
        code_dir = "some code dir"

        container = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock, mount_symlinks=True)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container
        self.func_config.runtime_management_config = dict(RuntimeVersionArn="runtime_version")
        self.runtime.create(self.func_config, debug_context=debug_options)
        LogMock.info.assert_called_once()
        # It shows a warning
        self.assertIn("This function will be invoked using the latest available runtime", LogMock.info.call_args[0][0])

        # Make sure env-vars get resolved
        self.env_vars.resolve.assert_called_with()

        # Make sure the context manager is called to return the code directory
        self.runtime._get_code_dir.assert_called_with(self.code_path)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=True,
        )
        # Run the container and get results
        self.manager_mock.create.assert_called_with(container, ContainerContext.INVOKE)


class LambdaRuntime_run(TestCase):
    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.manager_mock = Mock()
        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.layers = []
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "arm64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    def test_must_run_passed_container(self):
        container = Mock()
        container.is_running.return_value = False
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        self.runtime.run(container, self.func_config, debug_context=debug_options)
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)

    def test_must_create_container_first_if_passed_container_is_none(self):
        container = Mock()
        container.is_running.return_value = False
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)
        create_mock = Mock()
        self.runtime.create = create_mock
        create_mock.return_value = container

        self.runtime.run(None, self.func_config, debug_context=debug_options)
        create_mock.assert_called_with(
            function_config=self.func_config,
            debug_context=debug_options,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
        )
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)

    def test_must_skip_run_running_container(self):
        container = Mock()
        container.is_running.return_value = True
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        self.runtime.run(container, self.func_config, debug_context=debug_options)
        self.manager_mock.run.assert_not_called()

    def test_keyboard_interrupt_must_raise(self):
        container = Mock()
        container.is_running.return_value = False
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        self.manager_mock.run.side_effect = KeyboardInterrupt("some exception")

        with self.assertRaises(KeyboardInterrupt):
            self.runtime.run(container, self.func_config, debug_context=debug_options)


class LambdaRuntime_invoke(TestCase):
    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.manager_mock = Mock()

        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.layers = []
        self.architecture = "arm64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_run_container_and_wait_for_result(self, LambdaContainerMock):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        start_timer = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        self.runtime._clean_decompressed_paths = MagicMock()

        # Configure interrupt handler
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = start_timer

        self.runtime._check_exit_state = Mock()

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Make sure env-vars get resolved
        self.env_vars.resolve.assert_called_with()

        # Make sure the context manager is called to return the code directory
        self.runtime._get_code_dir.assert_called_with(self.code_path)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)
        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)
        container.wait_for_result.assert_called_with(
            event=event, full_path=self.full_path, stdout=stdout, stderr=stderr, start_timer=start_timer
        )

        # Finally block
        self.manager_mock.stop.assert_called_with(container)
        self.runtime._clean_decompressed_paths.assert_called_with()

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_exception_from_run_must_trigger_cleanup(self, LambdaContainerMock):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        start_timer = Mock()
        layer_downloader = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, layer_downloader)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = start_timer
        self.runtime._lock = MagicMock()

        self.runtime._check_exit_state = Mock()

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.manager_mock.run.side_effect = ValueError("some exception")

        with self.assertRaises(ValueError):
            self.runtime.invoke(self.func_config, event, debug_context=None, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)

        self.runtime._configure_interrupt.assert_not_called()

        # Finally block must be called
        # In any case, stop the container
        self.manager_mock.stop.assert_called_with(container)

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_exception_from_wait_for_result_must_trigger_cleanup(self, LambdaContainerMock):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        timer = Mock()
        debug_options = Mock()
        layer_downloader = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, layer_downloader)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer
        self.runtime._check_exit_state = Mock()
        self.runtime._lock = MagicMock()

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        container.wait_for_result.side_effect = ValueError("some exception")

        with self.assertRaises(ValueError):
            self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)

        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)

        # Finally block must be called
        # In any case, stop the container
        self.manager_mock.stop.assert_called_with(container)

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_keyboard_interrupt_must_not_raise(self, LambdaContainerMock):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        layer_downloader = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, layer_downloader)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._check_exit_state = Mock()
        self.runtime._lock = MagicMock()

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.manager_mock.run.side_effect = KeyboardInterrupt("some exception")

        self.runtime.invoke(self.func_config, event, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)

        self.runtime._configure_interrupt.assert_not_called()

        # Finally block must be called
        self.manager_mock.stop.assert_called_with(container)


class TestLambdaRuntime_configure_interrupt(TestCase):
    def setUp(self):
        self.name = "name"
        self.timeout = 123
        self.container = Mock()

        self.manager_mock = Mock()
        self.layer_downloader = Mock()
        self.runtime = LambdaRuntime(self.manager_mock, self.layer_downloader)

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_must_setup_timer(self, SignalMock, ThreadingMock):
        is_debugging = False  # We are not debugging. So setup timer
        timer_obj = Mock()
        ThreadingMock.Timer.return_value = timer_obj

        result_start_timer = self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)
        result_timer = result_start_timer()

        self.assertEqual(result_timer, timer_obj)

        ThreadingMock.Timer.assert_called_with(self.timeout, ANY, ())
        timer_obj.start.assert_called_with()

        SignalMock.signal.assert_not_called()  # must not setup signal handler

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_must_setup_signal_handler(self, SignalMock, ThreadingMock):
        is_debugging = True  # We are debugging. So setup signal
        SignalMock.SIGTERM = sigterm = "sigterm"

        result = self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)

        self.assertIsNone(result, "There are no return values when setting up signal handler")

        SignalMock.signal.assert_called_with(sigterm, ANY)
        ThreadingMock.Timer.signal.assert_not_called()  # must not setup timer

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_verify_signal_handler(self, SignalMock, ThreadingMock):
        """
        Verify the internal implementation of the Signal Handler
        """
        is_debugging = True  # We are debugging. So setup signal
        SignalMock.SIGTERM = "sigterm"

        # Fake the real method with a Lambda. Also run the handler immediately.
        SignalMock.signal = lambda term, handler: handler("a", "b")

        self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)

        # This method should be called from within the Signal Handler
        self.manager_mock.stop.assert_called_with(self.container)

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_verify_timer_handler(self, SignalMock, ThreadingMock):
        """
        Verify the internal implementation of the Signal Handler
        """
        is_debugging = False

        def fake_timer(timeout, handler, args):
            handler()
            return Mock()

        # Fake the real method with a Lambda. Also run the handler immediately.
        ThreadingMock.Timer = fake_timer

        start_timer = self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)
        start_timer()

        # This method should be called from within the Timer Handler
        self.manager_mock.stop.assert_called_with(self.container)


class TestLambdaRuntime_get_code_dir(TestCase):
    def setUp(self):
        self.manager_mock = Mock()
        self.layer_downloader = Mock()
        self.runtime = LambdaRuntime(self.manager_mock, self.layer_downloader)

    @parameterized.expand([(".zip"), (".ZIP"), (".JAR"), (".jar")])
    @patch("samcli.local.lambdafn.runtime.os")
    @patch("samcli.local.lambdafn.runtime.shutil")
    @patch("samcli.local.lambdafn.runtime._unzip_file")
    def test_must_uncompress_zip_files(self, extension, unzip_file_mock, shutil_mock, os_mock):
        code_path = "foo" + extension
        decompressed_dir = "decompressed-dir"

        unzip_file_mock.return_value = decompressed_dir
        os_mock.path.isfile.return_value = True

        result = self.runtime._get_code_dir(code_path)
        self.assertEqual(result, decompressed_dir)

        unzip_file_mock.assert_called_with(code_path)
        os_mock.path.isfile.assert_called_with(code_path)

    @patch("samcli.local.lambdafn.runtime.os")
    @patch("samcli.local.lambdafn.runtime.shutil")
    @patch("samcli.local.lambdafn.runtime._unzip_file")
    def test_must_return_a_valid_file(self, unzip_file_mock, shutil_mock, os_mock):
        """
        Input is a file that exists, but is not a zip/jar file
        """
        code_path = "foo.exe"

        os_mock.path.isfile.return_value = True

        result = self.runtime._get_code_dir(code_path)
        # code path must be returned. No decompression
        self.assertEqual(result, code_path)

        unzip_file_mock.assert_not_called()  # Unzip must not be called
        os_mock.path.isfile.assert_called_with(code_path)

        # Because we never unzipped anything, we should never delete
        shutil_mock.rmtree.assert_not_called()


class TestLambdaRuntime_unarchived_layer(TestCase):
    def setUp(self):
        self.manager_mock = Mock()
        self.layer_downloader = Mock()
        self.runtime = LambdaRuntime(self.manager_mock, self.layer_downloader)

    @parameterized.expand([(LayerVersion("arn", "file.zip"),)])
    @patch("samcli.local.lambdafn.runtime.LambdaRuntime._get_code_dir")
    def test_unarchived_layer(self, layer, get_code_dir_mock):
        new_url = get_code_dir_mock.return_value = Mock()
        result = self.runtime._unarchived_layer(layer)
        self.assertNotEqual(layer, result)
        self.assertEqual(new_url, result.codeuri)

    @parameterized.expand([("arn",), (LayerVersion("arn", "folder"),), ({"Name": "hi", "Version": "x.y.z"},)])
    @patch("samcli.local.lambdafn.runtime.LambdaRuntime._get_code_dir")
    def test_unarchived_layer_not_local_archive_file(self, layer, get_code_dir_mock):
        get_code_dir_mock.side_effect = lambda x: x  # directly return the input
        result = self.runtime._unarchived_layer(layer)
        self.assertEqual(layer, result)


class TestWarmLambdaRuntime_invoke(TestCase):
    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.manager_mock = Mock()

        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.layers = []
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "arm64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_run_container_then_wait_for_result_and_container_not_stopped(
        self, LambdaContainerMock, LambdaFunctionObserverMock
    ):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        start_timer = Mock()
        debug_options = Mock()
        debug_options.debug_function = self.name
        lambda_image_mock = Mock()

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        # Configure interrupt handler
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = start_timer

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Verify if Lambda Event data is set
        self.env_vars.add_lambda_event_body.assert_not_called()

        # Make sure env-vars get resolved
        self.env_vars.resolve.assert_called_with()

        # Make sure the context manager is called to return the code directory
        self.runtime._get_code_dir.assert_called_with(self.code_path)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container, ContainerContext.INVOKE)
        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)
        container.wait_for_result.assert_called_with(
            event=event, full_path=self.full_path, stdout=stdout, stderr=stderr, start_timer=start_timer
        )

        # Finally block
        self.manager_mock.stop.assert_not_called()


class TestWarmLambdaRuntime_create(TestCase):
    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.manager_mock = Mock()
        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.handler2 = "handler2"
        self.code_path = "code-path"
        self.layers = []
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "arm64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.func_config2 = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler2,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.func_config2.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_create_non_cached_container(self, LambdaContainerMock, LambdaFunctionObserverMock):
        code_dir = "some code dir"
        container = Mock()
        debug_options = Mock()
        debug_options.debug_function = self.name
        lambda_image_mock = Mock()

        lambda_function_observer_mock = Mock()
        LambdaFunctionObserverMock.return_value = lambda_function_observer_mock

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container

        self.runtime.create(self.func_config, debug_context=debug_options)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=debug_options,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )

        self.manager_mock.create.assert_called_with(container, ContainerContext.INVOKE)
        # validate that the created container got cached
        self.assertEqual(self.runtime._containers[self.full_path], container)
        lambda_function_observer_mock.watch.assert_called_with(self.func_config)
        lambda_function_observer_mock.start.assert_called_with()

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_create_incase_function_config_changed(self, LambdaContainerMock, LambdaFunctionObserverMock):
        code_dir = "some code dir"
        container = Mock()
        container2 = Mock()
        debug_options = Mock()
        debug_options.debug_function = self.name
        lambda_image_mock = Mock()

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.side_effect = [container, container2]
        self.runtime.create(self.func_config, debug_context=debug_options)
        result = self.runtime.create(self.func_config2, debug_context=debug_options)

        LambdaContainerMock.assert_has_calls(
            [
                call(
                    self.lang,
                    self.imageuri,
                    self.handler,
                    self.packagetype,
                    self.imageconfig,
                    code_dir,
                    self.layers,
                    lambda_image_mock,
                    self.architecture,
                    debug_options=debug_options,
                    env_vars=self.env_var_value,
                    memory_mb=self.DEFAULT_MEMORY,
                    container_host=None,
                    container_host_interface=None,
                    extra_hosts=None,
                    function_full_path=self.full_path,
                    mount_symlinks=False,
                ),
                call(
                    self.lang,
                    self.imageuri,
                    self.handler2,
                    self.packagetype,
                    self.imageconfig,
                    code_dir,
                    self.layers,
                    lambda_image_mock,
                    self.architecture,
                    debug_options=debug_options,
                    env_vars=self.env_var_value,
                    memory_mb=self.DEFAULT_MEMORY,
                    container_host=None,
                    container_host_interface=None,
                    extra_hosts=None,
                    function_full_path=self.full_path,
                    mount_symlinks=False,
                ),
            ]
        )

        self.manager_mock.create.assert_has_calls(
            [call(container, ContainerContext.INVOKE), call(container2, ContainerContext.INVOKE)]
        )
        self.manager_mock.stop.assert_called_with(container)
        # validate that the created container got cached
        self.assertEqual(self.runtime._containers[self.full_path], container2)
        self.assertEqual(result, container2)

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_return_cached_container(self, LambdaContainerMock, LambdaFunctionObserverMock):
        code_dir = "some code dir"
        container = Mock()
        debug_options = Mock()
        debug_options.debug_function = self.name
        lambda_image_mock = Mock()

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container
        self.runtime.create(self.func_config, debug_context=debug_options)
        result = self.runtime.create(self.func_config, debug_context=debug_options)

        # validate that the manager.create method got called only one time
        self.manager_mock.create.assert_called_once_with(container, ContainerContext.INVOKE)
        self.assertEqual(result, container)

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_ignore_debug_options_if_function_name_is_not_debug_function(
        self, LambdaContainerMock, LambdaFunctionObserverMock
    ):
        code_dir = "some code dir"
        container = Mock()
        debug_options = Mock()
        debug_options.debug_function = "name2"
        lambda_image_mock = Mock()

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container

        self.runtime.create(self.func_config, debug_context=debug_options)

        # Make sure the container is created with proper values
        LambdaContainerMock.assert_called_with(
            self.lang,
            self.imageuri,
            self.handler,
            self.packagetype,
            self.imageconfig,
            code_dir,
            self.layers,
            lambda_image_mock,
            self.architecture,
            debug_options=None,
            env_vars=self.env_var_value,
            memory_mb=self.DEFAULT_MEMORY,
            container_host=None,
            container_host_interface=None,
            extra_hosts=None,
            function_full_path=self.full_path,
            mount_symlinks=False,
        )
        self.manager_mock.create.assert_called_with(container, ContainerContext.INVOKE)
        # validate that the created container got cached
        self.assertEqual(self.runtime._containers[self.full_path], container)


class TestWarmLambdaRuntime_get_code_dir(TestCase):
    def setUp(self):
        self.manager_mock = Mock()

    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_return_same_path_if_path_is_not_compressed_file(self, os_mock):
        lambda_image_mock = Mock()
        observer_mock = Mock()
        os_mock.path.isfile.return_value = False
        code_path = "path"

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock, observer_mock)
        res = self.runtime._get_code_dir(code_path)
        self.assertEqual(self.runtime._temp_uncompressed_paths_to_be_cleaned, [])
        self.assertEqual(res, code_path)

    @patch("samcli.local.lambdafn.runtime._unzip_file")
    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_cache_temp_uncompressed_dirs_to_be_cleared_later(self, os_mock, _unzip_file_mock):
        lambda_image_mock = Mock()
        observer_mock = Mock()
        os_mock.path.isfile.return_value = True
        uncompressed_dir_mock = Mock()
        _unzip_file_mock.return_value = uncompressed_dir_mock
        code_path = "path.zip"

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock, observer_mock)
        res = self.runtime._get_code_dir(code_path)
        self.assertEqual(self.runtime._temp_uncompressed_paths_to_be_cleaned, [uncompressed_dir_mock])
        self.assertEqual(res, uncompressed_dir_mock)


class TestWarmLambdaRuntime_clean_warm_containers_related_resources(TestCase):
    def setUp(self):
        self.manager_mock = Mock()
        lambda_image_mock = Mock()
        self.observer_mock = Mock()
        self.observer_mock.is_alive.return_value = True
        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock, self.observer_mock)

        self.func1_container_mock = Mock()
        self.func2_container_mock = Mock()
        self.runtime._containers = {
            "func_name1": self.func1_container_mock,
            "func_name2": self.func2_container_mock,
        }
        self.runtime._temp_uncompressed_paths_to_be_cleaned = ["path1", "path2"]
        self.runtime._lock = MagicMock()

    @patch("samcli.local.lambdafn.runtime.shutil")
    def test_must_container_stopped_when_its_code_dir_got_changed(self, shutil_mock):
        self.runtime.clean_running_containers_and_related_resources()
        self.assertEqual(
            self.runtime._container_manager.stop.call_args_list,
            [
                call(self.func1_container_mock),
                call(self.func2_container_mock),
            ],
        )
        self.assertEqual(
            shutil_mock.rmtree.call_args_list,
            [
                call("path1"),
                call("path2"),
            ],
        )
        self.runtime._observer.stop.assert_called_once_with()


class TestWarmLambdaRuntime_on_code_change(TestCase):
    def setUp(self):
        self.manager_mock = Mock()
        lambda_image_mock = Mock()
        self.observer_mock = Mock()
        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock, self.observer_mock)

        self.lang = "runtime"
        self.handler = "handler"
        self.imageuri = None
        self.imageconfig = None
        self.architecture = "arm64"

        self.func1_name = "func1_name"
        self.func1_full_path = "stack/func1_name"
        self.func1_code_path = "func1_code_path"

        self.func2_name = "func2_name"
        self.func2_full_path = "stack/func2_name"
        self.func2_code_path = "func2_code_path"

        self.common_layer_code_path = "layer1-code-path"
        self.common_layer_arn = "layer1-arn"
        self.common_layers = [
            LayerVersion(arn=self.common_layer_arn, codeuri=self.common_layer_code_path, compatible_runtimes=self.lang)
        ]

        self.func_config1 = FunctionConfig(
            self.func1_name,
            self.func1_full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            ZIP,
            self.func1_code_path,
            self.common_layers,
            self.architecture,
        )
        self.func_config2 = FunctionConfig(
            self.func2_name,
            self.func2_full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            IMAGE,
            self.func2_code_path,
            self.common_layers,
            self.architecture,
        )

        self.func1_container_mock = Mock()
        self.func2_container_mock = Mock()
        self.runtime._containers = {
            self.func1_full_path: self.func1_container_mock,
            self.func2_full_path: self.func2_container_mock,
        }

    def test_only_one_container_get_stopped_when_its_code_dir_got_changed(self):
        self.runtime._on_code_change([self.func_config1])

        self.manager_mock.stop.assert_called_with(self.func1_container_mock)
        self.assertEqual(
            self.runtime._containers,
            {
                self.func2_full_path: self.func2_container_mock,
            },
        )

        self.observer_mock.unwatch.assert_called_with(self.func_config1)

    def test_both_containers_get_stopped_when_both_functions_got_updated(self):
        self.runtime._on_code_change([self.func_config1, self.func_config2])

        self.assertEqual(
            self.manager_mock.stop.call_args_list,
            [
                call(self.func1_container_mock),
                call(self.func2_container_mock),
            ],
        )
        self.assertEqual(self.runtime._containers, {})

        self.assertEqual(
            self.observer_mock.unwatch.call_args_list,
            [
                call(self.func_config1),
                call(self.func_config2),
            ],
        )


class TestUnzipFile(TestCase):
    @patch("samcli.local.lambdafn.runtime.tempfile")
    @patch("samcli.local.lambdafn.runtime.unzip")
    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_unzip_not_posix(self, os_mock, unzip_mock, tempfile_mock):
        inputpath = "somepath"
        tmpdir = "/tmp/dir"
        realpath = "/foo/bar/tmp/dir/code.zip"

        tempfile_mock.mkdtemp.return_value = tmpdir
        os_mock.path.realpath.return_value = realpath
        os_mock.name = "not-posix"

        output = _unzip_file(inputpath)
        self.assertEqual(output, realpath)

        tempfile_mock.mkdtemp.assert_called_with()
        unzip_mock.assert_called_with(inputpath, tmpdir)  # unzip files to temporary directory
        os_mock.path.realpath(tmpdir)  # Return the real path of temporary directory
        os_mock.chmod.assert_not_called()  # Assert we do not chmod the temporary directory

    @patch("samcli.local.lambdafn.runtime.tempfile")
    @patch("samcli.local.lambdafn.runtime.unzip")
    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_unzip_posix(self, os_mock, unzip_mock, tempfile_mock):
        inputpath = "somepath"
        tmpdir = "/tmp/dir"
        realpath = "/foo/bar/tmp/dir/code.zip"

        tempfile_mock.mkdtemp.return_value = tmpdir
        os_mock.path.realpath.return_value = realpath
        os_mock.name = "posix"

        output = _unzip_file(inputpath)
        self.assertEqual(output, realpath)

        tempfile_mock.mkdtemp.assert_called_with()
        unzip_mock.assert_called_with(inputpath, tmpdir)  # unzip files to temporary directory
        os_mock.path.realpath(tmpdir)  # Return the real path of temporary directory
        os_mock.chmod.assert_called_with(tmpdir, 0o755)  # Assert we do chmod the temporary directory


class TestRequireContainerReloading(TestCase):
    def test_function_should_reloaded_if_runtime_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.8",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_handler_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler1",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_package_type_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            "imageUri",
            None,
            IMAGE,
            None,
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_image_uri_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            "imageUri",
            None,
            IMAGE,
            None,
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            "imageUri1",
            None,
            IMAGE,
            None,
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_image_config_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            "imageUri",
            {"WorkingDirectory": "/opt"},
            IMAGE,
            None,
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            "imageUri",
            {"WorkingDirectory": "/var"},
            IMAGE,
            None,
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_code_path_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code2",
            [],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_env_vars_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
            env_vars=EnvironmentVariables(
                variables={
                    "key1": "value1",
                    "key2": "value2",
                }
            ),
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [],
            "x86_64",
            env_vars=EnvironmentVariables(
                variables={
                    "key1": "value1",
                }
            ),
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_one_layer_removed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("ServerlessLayer", "/somepath2", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("ServerlessLayer", "/somepath2", stack_path=""),
            ],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_one_layer_added(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("ServerlessLayer", "/somepath2", stack_path=""),
            ],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_reloaded_if_layers_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath2", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )
        self.assertTrue(_require_container_reloading(func, updated_func))

    def test_function_should_not_reloaded_if_nothing_changed(self):
        func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("ServerlessLayer", "/somepath2", stack_path=""),
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )

        updated_func = FunctionConfig(
            "name",
            "stack/name",
            "python3.12",
            "app.handler",
            None,
            None,
            ZIP,
            "/code",
            [
                LayerVersion("Layer", "/somepath", stack_path=""),
                LayerVersion("ServerlessLayer", "/somepath2", stack_path=""),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=""),
            ],
            "x86_64",
        )
        self.assertFalse(_require_container_reloading(func, updated_func))


class TestLambdaRuntime_create_exceptions(TestCase):
    """Test exception handling in LambdaRuntime.create method"""

    def setUp(self):
        self.manager_mock = Mock()
        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.layers = []
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "x86_64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LOG")
    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_docker_container_creation_failed_exception_must_raise_and_log(self, LambdaContainerMock, LogMock):
        """Test DockerContainerCreationFailedException handling - lines 130-131"""
        from samcli.local.docker.exceptions import DockerContainerCreationFailedException

        code_dir = "some code dir"
        container = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        LambdaContainerMock.return_value = container
        self.manager_mock.create.side_effect = DockerContainerCreationFailedException("Container creation failed")

        with self.assertRaises(DockerContainerCreationFailedException):
            self.runtime.create(self.func_config, debug_context=debug_options)

        # Verify the warning log was called
        LogMock.warning.assert_called_once_with("Failed to create container for function %s", self.full_path)


class TestLambdaRuntime_check_exit_state(TestCase):
    """Test _check_exit_state method - lines 299-302"""

    def setUp(self):
        self.manager_mock = Mock()
        self.lambda_image_mock = Mock()
        self.runtime = LambdaRuntime(self.manager_mock, self.lambda_image_mock)

    @patch("samcli.local.lambdafn.runtime.ContainerAnalyzer")
    def test_check_exit_state_out_of_memory_raises_exception(self, ContainerAnalyzerMock):
        """Test that out of memory condition raises ContainerFailureError"""
        from samcli.local.docker.exceptions import ContainerFailureError

        container = Mock()
        analyzer_mock = Mock()
        exit_state_mock = Mock()
        exit_state_mock.out_of_memory = True

        ContainerAnalyzerMock.return_value = analyzer_mock
        analyzer_mock.inspect.return_value = exit_state_mock

        with self.assertRaises(ContainerFailureError) as context:
            self.runtime._check_exit_state(container)

        self.assertEqual(str(context.exception), "Container invocation failed due to maximum memory usage")
        ContainerAnalyzerMock.assert_called_once_with(self.manager_mock, container)
        analyzer_mock.inspect.assert_called_once()

    @patch("samcli.local.lambdafn.runtime.ContainerAnalyzer")
    def test_check_exit_state_normal_exit_no_exception(self, ContainerAnalyzerMock):
        """Test that normal exit doesn't raise exception"""
        container = Mock()
        analyzer_mock = Mock()
        exit_state_mock = Mock()
        exit_state_mock.out_of_memory = False

        ContainerAnalyzerMock.return_value = analyzer_mock
        analyzer_mock.inspect.return_value = exit_state_mock

        # Should not raise any exception
        self.runtime._check_exit_state(container)

        ContainerAnalyzerMock.assert_called_once_with(self.manager_mock, container)
        analyzer_mock.inspect.assert_called_once()


class TestLambdaRuntime_on_invoke_done_with_container(TestCase):
    """Test _on_invoke_done method when container is provided - lines 279->282"""

    def setUp(self):
        self.manager_mock = Mock()
        self.lambda_image_mock = Mock()
        self.runtime = LambdaRuntime(self.manager_mock, self.lambda_image_mock)

    def test_on_invoke_done_with_container_calls_check_exit_state_and_stop(self):
        """Test that _on_invoke_done calls _check_exit_state and stops container when container is provided"""
        container = Mock()

        # Mock the _check_exit_state method
        self.runtime._check_exit_state = Mock()
        self.runtime._clean_decompressed_paths = Mock()

        self.runtime._on_invoke_done(container)

        # Verify _check_exit_state was called
        self.runtime._check_exit_state.assert_called_once_with(container)
        # Verify container was stopped
        self.manager_mock.stop.assert_called_once_with(container)
        # Verify cleanup was called
        self.runtime._clean_decompressed_paths.assert_called_once()

    def test_on_invoke_done_with_none_container_only_cleans_paths(self):
        """Test that _on_invoke_done only cleans paths when container is None"""
        self.runtime._check_exit_state = Mock()
        self.runtime._clean_decompressed_paths = Mock()

        self.runtime._on_invoke_done(None)

        # Verify _check_exit_state was not called
        self.runtime._check_exit_state.assert_not_called()
        # Verify container stop was not called
        self.manager_mock.stop.assert_not_called()
        # Verify cleanup was called
        self.runtime._clean_decompressed_paths.assert_called_once()


class TestWarmLambdaRuntime_create_container_branch(TestCase):
    """Test WarmLambdaRuntime.create method container branch - lines 470->473"""

    def setUp(self):
        self.manager_mock = Mock()
        self.lambda_image_mock = Mock()
        self.observer_mock = Mock()
        self.runtime = WarmLambdaRuntime(self.manager_mock, self.lambda_image_mock, observer=self.observer_mock)

        self.name = "name"
        self.full_path = "stack/name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.layers = []
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.architecture = "x86_64"
        self.func_config = FunctionConfig(
            self.name,
            self.full_path,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.env_vars = Mock()
        self.func_config.env_vars = self.env_vars
        self.env_var_value = {"a": "b"}
        self.env_vars.resolve.return_value = self.env_var_value

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_create_with_existing_config_and_no_container_stops_none_container(self, LambdaContainerMock):
        """Test create method when existing config requires reloading but container is None - lines 470->473"""
        # Setup existing function config that requires reloading
        existing_config = FunctionConfig(
            self.name,
            self.full_path,
            "different_runtime",  # Different runtime to trigger reloading
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )
        existing_config.env_vars = self.env_vars

        # Set up existing config but no container
        self.runtime._function_configs[self.full_path] = existing_config
        self.runtime._containers[self.full_path] = None  # No container

        container = Mock()
        LambdaContainerMock.return_value = container

        # Mock parent create method
        with patch.object(LambdaRuntime, "create", return_value=container) as parent_create_mock:
            result = self.runtime.create(self.func_config)

        # Verify container stop was not called (since container was None)
        self.manager_mock.stop.assert_not_called()
        # Verify observer unwatch was called
        self.observer_mock.unwatch.assert_called_once_with(existing_config)
        # Verify new container was created and stored
        self.assertEqual(result, container)
        self.assertEqual(self.runtime._containers[self.full_path], container)
        # Verify new function config was stored (the old one was replaced)
        self.assertIn(self.full_path, self.runtime._function_configs)
        self.assertEqual(self.runtime._function_configs[self.full_path], self.func_config)


class TestWarmLambdaRuntime_configure_interrupt(TestCase):
    """Test WarmLambdaRuntime._configure_interrupt method - lines 534-554"""

    @patch("samcli.local.lambdafn.runtime.LambdaFunctionObserver")
    def setUp(self, LambdaFunctionObserverMock):
        self.manager_mock = Mock()
        self.lambda_image_mock = Mock()
        self.observer_mock = Mock()
        LambdaFunctionObserverMock.return_value = self.observer_mock
        self.runtime = WarmLambdaRuntime(self.manager_mock, self.lambda_image_mock)

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_configure_interrupt_debugging_mode_returns_none(self, SignalMock, ThreadingMock):
        """Test _configure_interrupt in debugging mode returns None and sets up signal handler"""
        function_full_path = "test/function"
        timeout = 30
        container = Mock()
        is_debugging = True

        SignalMock.SIGTERM = "sigterm"

        result = self.runtime._configure_interrupt(function_full_path, timeout, container, is_debugging)

        self.assertIsNone(result)
        SignalMock.signal.assert_called_once_with("sigterm", ANY)
        ThreadingMock.Timer.assert_not_called()

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_configure_interrupt_non_debugging_mode_returns_start_timer(self, SignalMock, ThreadingMock):
        """Test _configure_interrupt in non-debugging mode returns start_timer function"""
        function_full_path = "test/function"
        timeout = 30
        container = Mock()
        is_debugging = False

        result = self.runtime._configure_interrupt(function_full_path, timeout, container, is_debugging)

        self.assertIsNotNone(result)
        self.assertTrue(callable(result))
        SignalMock.signal.assert_not_called()

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_configure_interrupt_timer_handler_logs_timeout(self, SignalMock, ThreadingMock):
        """Test that timer handler logs timeout message but doesn't stop container in WarmLambdaRuntime"""
        function_full_path = "test/function"
        timeout = 30
        container = Mock()
        is_debugging = False

        def fake_timer(timeout_val, handler, args):
            # Execute the handler immediately to test it
            handler()
            return Mock()

        ThreadingMock.Timer = fake_timer

        with patch("samcli.local.lambdafn.runtime.LOG") as LogMock:
            start_timer = self.runtime._configure_interrupt(function_full_path, timeout, container, is_debugging)
            start_timer()

            # Verify timeout message was logged
            LogMock.info.assert_called_once_with(
                "Function '%s' timed out after %d seconds", function_full_path, timeout
            )
            # Verify container was NOT stopped (different from regular LambdaRuntime)
            self.manager_mock.stop.assert_not_called()

    @patch("samcli.local.lambdafn.runtime.threading")
    @patch("samcli.local.lambdafn.runtime.signal")
    def test_configure_interrupt_signal_handler_logs_interruption(self, SignalMock, ThreadingMock):
        """Test that signal handler logs interruption message but doesn't stop container in WarmLambdaRuntime"""
        function_full_path = "test/function"
        timeout = 30
        container = Mock()
        is_debugging = True

        SignalMock.SIGTERM = "sigterm"

        # Fake the signal.signal method to execute handler immediately
        def fake_signal(term, handler):
            handler("sig", "frame")

        SignalMock.signal = fake_signal

        with patch("samcli.local.lambdafn.runtime.LOG") as LogMock:
            self.runtime._configure_interrupt(function_full_path, timeout, container, is_debugging)

            # Verify interruption message was logged
            LogMock.info.assert_called_once_with("Execution of function %s was interrupted", function_full_path)
            # Verify container was NOT stopped (different from regular LambdaRuntime)
            self.manager_mock.stop.assert_not_called()


class TestWarmLambdaRuntime_on_code_change_container_branch(TestCase):
    """Test WarmLambdaRuntime._on_code_change method container branch - lines 589->577"""

    def setUp(self):
        self.manager_mock = Mock()
        self.lambda_image_mock = Mock()
        self.observer_mock = Mock()
        self.runtime = WarmLambdaRuntime(self.manager_mock, self.lambda_image_mock, observer=self.observer_mock)

        self.func_config = FunctionConfig(
            "name",
            "stack/function",
            "python3.9",
            "handler",
            None,
            None,
            ZIP,
            "code-path",
            [],
            "x86_64",
        )

    def test_on_code_change_with_no_container_doesnt_stop_container(self):
        """Test _on_code_change when no container exists for the function - lines 589->577"""
        # Set up function config but no container
        self.runtime._function_configs[self.func_config.full_path] = self.func_config
        self.runtime._containers[self.func_config.full_path] = None  # No container

        with patch("samcli.local.lambdafn.runtime.LOG") as LogMock:
            self.runtime._on_code_change([self.func_config])

        # Verify function config was removed
        self.assertNotIn(self.func_config.full_path, self.runtime._function_configs)
        # Verify container stop was not called (since container was None)
        self.manager_mock.stop.assert_not_called()
        # Verify observer unwatch was called
        self.observer_mock.unwatch.assert_called_once_with(self.func_config)
        # Verify log message was called
        LogMock.info.assert_called_once()

    def test_on_code_change_with_container_stops_container(self):
        """Test _on_code_change when container exists for the function"""
        container = Mock()

        # Set up function config and container
        self.runtime._function_configs[self.func_config.full_path] = self.func_config
        self.runtime._containers[self.func_config.full_path] = container

        with patch("samcli.local.lambdafn.runtime.LOG") as LogMock:
            self.runtime._on_code_change([self.func_config])

        # Verify function config was removed
        self.assertNotIn(self.func_config.full_path, self.runtime._function_configs)
        # Verify container was removed
        self.assertNotIn(self.func_config.full_path, self.runtime._containers)
        # Verify container stop was called
        self.manager_mock.stop.assert_called_once_with(container)
        # Verify observer unwatch was called
        self.observer_mock.unwatch.assert_called_once_with(self.func_config)
        # Verify log message was called
        LogMock.info.assert_called_once()

    def test_on_code_change_with_image_package_type_logs_image_resource(self):
        """Test _on_code_change logs correct resource type for IMAGE package type"""
        from samcli.lib.utils.packagetype import IMAGE

        # Create function config with IMAGE package type
        image_func_config = FunctionConfig(
            "name",
            "stack/function",
            "python3.9",
            "handler",
            "my-image:latest",
            None,
            IMAGE,
            "code-path",
            [],
            "x86_64",
        )

        container = Mock()
        self.runtime._function_configs[image_func_config.full_path] = image_func_config
        self.runtime._containers[image_func_config.full_path] = container

        with patch("samcli.local.lambdafn.runtime.LOG") as LogMock:
            self.runtime._on_code_change([image_func_config])

        # Verify log message contains image reference
        LogMock.info.assert_called_once()
        log_call_args = LogMock.info.call_args[0]
        # The log format is: "Lambda Function '%s' %s has been changed..."
        # where %s is function_full_path and %s is resource (imageuri + " image")
        self.assertIn("my-image:latest image", log_call_args[2])
