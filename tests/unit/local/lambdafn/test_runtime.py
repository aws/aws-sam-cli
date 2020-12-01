"""
Unit tests for Lambda runtime
"""

from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, ANY
from parameterized import parameterized

from samcli.lib.utils.packagetype import ZIP
from samcli.local.lambdafn.runtime import LambdaRuntime, _unzip_file
from samcli.local.lambdafn.config import FunctionConfig


class LambdaRuntime_invoke(TestCase):

    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):

        self.manager_mock = Mock()

        self.name = "name"
        self.lang = "runtime"
        self.handler = "handler"
        self.code_path = "code-path"
        self.imageuri = None
        self.packagetype = ZIP
        self.imageconfig = None
        self.layers = []
        self.func_config = FunctionConfig(
            self.name,
            self.lang,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
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
        self.runtime._get_code_dir(self.code_path).__enter__.return_value = code_dir

        # Configure interrupt handler
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

        LambdaContainerMock.return_value = container

        self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Verify if Lambda Event data is set
        self.env_vars.add_lambda_event_body.assert_called_with(event)

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
            memory_mb=self.DEFAULT_MEMORY,
            env_vars=self.env_var_value,
            debug_options=debug_options,
        )

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)
        self.runtime._configure_interrupt.assert_called_with(self.name, self.DEFAULT_TIMEOUT, container, True)
        container.wait_for_result.assert_called_with(event=event, name=self.name, stdout=stdout, stderr=stderr)

        # Finally block
        timer.cancel.assert_called_with()
        self.manager_mock.stop.assert_called_with(container)

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
        self.runtime._get_code_dir(self.code_path).__enter__.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

        LambdaContainerMock.return_value = container

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
    def test_exception_from_wait_for_logs_must_trigger_cleanup(self, LambdaContainerMock):
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
        self.runtime._get_code_dir(self.code_path).__enter__.return_value = code_dir
        self.runtime._configure_interrupt = Mock()
        self.runtime._configure_interrupt.return_value = timer

        LambdaContainerMock.return_value = container

        container.wait_for_result.side_effect = ValueError("some exception")

        with self.assertRaises(ValueError):
            self.runtime.invoke(self.func_config, event, debug_context=debug_options, stdout=stdout, stderr=stderr)

        # Run the container and get results
        self.manager_mock.run.assert_called_with(container)

        self.runtime._configure_interrupt.assert_called_with(self.name, self.DEFAULT_TIMEOUT, container, True)

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
        self.runtime._get_code_dir(self.code_path).__enter__.return_value = code_dir
        self.runtime._configure_interrupt = Mock()

        LambdaContainerMock.return_value = container

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

        with self.runtime._get_code_dir(code_path) as result:
            self.assertEqual(result, decompressed_dir)

        unzip_file_mock.assert_called_with(code_path)
        os_mock.path.isfile.assert_called_with(code_path)

        # Finally block must call this after the context manager exists
        shutil_mock.rmtree.assert_called_with(decompressed_dir)

    @patch("samcli.local.lambdafn.runtime.os")
    @patch("samcli.local.lambdafn.runtime.shutil")
    @patch("samcli.local.lambdafn.runtime._unzip_file")
    def test_must_return_a_valid_file(self, unzip_file_mock, shutil_mock, os_mock):
        """
        Input is a file that exists, but is not a zip/jar file
        """
        code_path = "foo.exe"

        os_mock.path.isfile.return_value = True

        with self.runtime._get_code_dir(code_path) as result:
            # code path must be returned. No decompression
            self.assertEqual(result, code_path)

        unzip_file_mock.assert_not_called()  # Unzip must not be called
        os_mock.path.isfile.assert_called_with(code_path)

        # Because we never unzipped anything, we should never delete
        shutil_mock.rmtree.assert_not_called()


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
