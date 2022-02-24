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

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_must_create_lambda_container(self, LambdaContainerMock):
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
            function_full_path=self.full_path,
        )
        # Run the container and get results
        self.manager_mock.create.assert_called_with(container)

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
        self.manager_mock.run.assert_called_with(container)

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
        create_mock.assert_called_with(self.func_config, debug_options, None, None)
        self.manager_mock.run.assert_called_with(container)

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
        timer = Mock()
        debug_options = Mock()
        lambda_image_mock = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        self.runtime._clean_decompressed_paths = MagicMock()

        # Configure interrupt handler
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

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
            function_full_path=self.full_path,
        )

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)
        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)
        container.wait_for_result.assert_called_with(
            event=event, full_path=self.full_path, stdout=stdout, stderr=stderr
        )

        # Finally block
        timer.cancel.assert_called_with()
        self.manager_mock.stop.assert_called_with(container)
        self.runtime._clean_decompressed_paths.assert_called_with()

    @patch("samcli.local.lambdafn.runtime.LambdaContainer")
    def test_exception_from_run_must_trigger_cleanup(self, LambdaContainerMock):
        event = "event"
        code_dir = "some code dir"
        stdout = "stdout"
        stderr = "stderr"
        container = Mock()
        timer = Mock()
        layer_downloader = Mock()

        self.runtime = LambdaRuntime(self.manager_mock, layer_downloader)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.manager_mock.run.side_effect = ValueError("some exception")

        with self.assertRaises(ValueError):
            self.runtime.invoke(self.func_config, event, debug_context=None, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)

        self.runtime._configure_interrupt.assert_not_called()

        # Finally block must be called
        # But timer was not yet created. It should not be called
        timer.cancel.assert_not_called()
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

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        container.wait_for_result.side_effect = ValueError("some exception")

        with self.assertRaises(ValueError):
            self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)

        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)

        # Finally block must be called
        # Timer was created. So it must be cancelled
        timer.cancel.assert_called_with()
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

        LambdaContainerMock.return_value = container
        container.is_running.return_value = False

        self.manager_mock.run.side_effect = KeyboardInterrupt("some exception")

        self.runtime.invoke(self.func_config, event, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)

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

        result = self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)

        self.assertEqual(result, timer_obj)

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

        self.runtime._configure_interrupt(self.name, self.timeout, self.container, is_debugging)

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
        timer = Mock()
        debug_options = Mock()
        debug_options.debug_function = self.name
        lambda_image_mock = Mock()

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        # Using MagicMock to mock the context manager
        self.runtime._get_code_dir = MagicMock()
        self.runtime._get_code_dir.return_value = code_dir

        # Configure interrupt handler
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

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
            function_full_path=self.full_path,
        )

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)
        self.runtime._configure_interrupt.assert_called_with(self.full_path, self.DEFAULT_TIMEOUT, container, True)
        container.wait_for_result.assert_called_with(
            event=event, full_path=self.full_path, stdout=stdout, stderr=stderr
        )

        # Finally block
        timer.cancel.assert_called_with()
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
            function_full_path=self.full_path,
        )

        self.manager_mock.create.assert_called_with(container)
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
                    function_full_path=self.full_path,
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
                    function_full_path=self.full_path,
                ),
            ]
        )

        self.manager_mock.create.assert_has_calls([call(container), call(container2)])
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
        self.manager_mock.create.assert_called_once_with(container)
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
            function_full_path=self.full_path,
        )
        self.manager_mock.create.assert_called_with(container)
        # validate that the created container got cached
        self.assertEqual(self.runtime._containers[self.full_path], container)


class TestWarmLambdaRuntime_get_code_dir(TestCase):
    def setUp(self):
        self.manager_mock = Mock()

    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_return_same_path_if_path_is_not_compressed_file(self, os_mock):
        lambda_image_mock = Mock()
        os_mock.path.isfile.return_value = False
        code_path = "path"

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)
        res = self.runtime._get_code_dir(code_path)
        self.assertEqual(self.runtime._temp_uncompressed_paths_to_be_cleaned, [])
        self.assertEqual(res, code_path)

    @patch("samcli.local.lambdafn.runtime._unzip_file")
    @patch("samcli.local.lambdafn.runtime.os")
    def test_must_cache_temp_uncompressed_dirs_to_be_cleared_later(self, os_mock, _unzip_file_mock):
        lambda_image_mock = Mock()
        os_mock.path.isfile.return_value = True
        uncompressed_dir_mock = Mock()
        _unzip_file_mock.return_value = uncompressed_dir_mock
        code_path = "path.zip"

        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)
        res = self.runtime._get_code_dir(code_path)
        self.assertEqual(self.runtime._temp_uncompressed_paths_to_be_cleaned, [uncompressed_dir_mock])
        self.assertEqual(res, uncompressed_dir_mock)


class TestWarmLambdaRuntime_clean_warm_containers_related_resources(TestCase):
    def setUp(self):
        self.manager_mock = Mock()
        lambda_image_mock = Mock()
        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)
        self.observer_mock = Mock()
        self.func1_container_mock = Mock()
        self.func2_container_mock = Mock()
        self.runtime._containers = {
            "func_name1": self.func1_container_mock,
            "func_name2": self.func2_container_mock,
        }
        self.runtime._observer = self.observer_mock
        self.runtime._observer.is_alive.return_value = True
        self.runtime._temp_uncompressed_paths_to_be_cleaned = ["path1", "path2"]

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
        self.runtime = WarmLambdaRuntime(self.manager_mock, lambda_image_mock)

        self.observer_mock = Mock()
        self.runtime._observer = self.observer_mock

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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
            "python3.7",
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
