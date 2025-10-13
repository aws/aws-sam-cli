"""
Unit tests for platform_config module
"""

import plistlib
import unittest
from unittest.mock import patch, mock_open, Mock
from parameterized import parameterized

from samcli.local.docker.platform_config import MacOSHandler, LinuxHandler, WindowsHandler, get_platform_handler
from samcli.local.docker.container_engine import ContainerEngine


class TestPlatformHandlerBase(unittest.TestCase):
    """Unit tests for PlatformHandler base class"""

    def test_read_config_with_none_from_subclass(self):
        """Test read_config when _read_config returns None"""
        handler = MacOSHandler()
        with patch.object(handler, "_read_config", return_value=None):
            result = handler.read_config()
            self.assertIsNone(result)

    def test_read_config_with_whitespace_value(self):
        """Test read_config strips whitespace and converts to lowercase"""
        handler = MacOSHandler()
        with patch.object(handler, "_read_config", return_value="  DOCKER  "):
            result = handler.read_config()
            self.assertEqual(result, "docker")


class TestMacOSHandler(unittest.TestCase):
    """Unit tests for MacOSHandler"""

    def setUp(self):
        self.handler = MacOSHandler()

    def test_read_config_success_with_finch(self):
        """Test successful plist reading with finch preference"""
        mock_plist_data = {"DefaultContainerRuntime": "finch"}

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value=mock_plist_data
        ):
            result = self.handler.read_config()
            self.assertEqual(result, "finch")

    def test_read_config_success_with_docker(self):
        """Test successful plist reading with docker preference"""
        mock_plist_data = {"DefaultContainerRuntime": "docker"}

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value=mock_plist_data
        ):
            result = self.handler.read_config()
            self.assertEqual(result, "docker")

    def test_read_config_file_not_exists(self):
        """Test when plist file doesn't exist"""
        with patch("os.path.exists", return_value=False):
            result = self.handler.read_config()
            self.assertIsNone(result)

    def test_read_config_no_default_container_runtime_key(self):
        """Test when plist exists but has no DefaultContainerRuntime key"""
        mock_plist_data = {"SomeOtherKey": "value"}

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value=mock_plist_data
        ):
            result = self.handler.read_config()
            self.assertIsNone(result)

    @parameterized.expand(
        [
            (FileNotFoundError("File not found"),),
            (OSError("Permission denied"),),
            (plistlib.InvalidFileException("Invalid plist"),),
        ]
    )
    def test_read_config_exception_handling(self, exception):
        """Test exception handling during plist reading"""
        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", side_effect=exception
        ):
            result = self.handler.read_config()
            self.assertIsNone(result)

    def test_get_finch_socket_path(self):
        """Test macOS Finch socket path"""
        result = self.handler.get_finch_socket_path()
        self.assertEqual(result, "unix:////Applications/Finch/lima/data/finch/sock/finch.sock")

    def test_supports_finch(self):
        """Test that macOS supports Finch"""
        self.assertTrue(self.handler.supports_finch())

    def test_get_container_not_reachable_message_with_finch_preference(self):
        """Test macOS error message when admin preference is finch"""
        with patch.object(self.handler, "read_config", return_value="finch"):
            result = self.handler.get_container_not_reachable_message()
            self.assertEqual(
                result, "Running AWS SAM projects locally requires Finch. Do you have Finch installed and running?"
            )

    def test_get_container_not_reachable_message_with_docker_preference(self):
        """Test macOS error message when admin preference is docker"""
        with patch.object(self.handler, "read_config", return_value="docker"):
            result = self.handler.get_container_not_reachable_message()
            self.assertEqual(
                result, "Running AWS SAM projects locally requires Docker. Do you have Docker installed and running?"
            )

    def test_get_container_not_reachable_message_no_preference(self):
        """Test macOS error message when no admin preference is set"""
        with patch.object(self.handler, "read_config", return_value=None):
            result = self.handler.get_container_not_reachable_message()
            expected = (
                "Running AWS SAM projects locally requires a container runtime. "
                "Do you have Docker or Finch installed and running?"
            )
            self.assertEqual(result, expected)

    def test_read_config_with_none_container_runtime(self):
        """Test read_config when container_runtime is None"""
        mock_plist_data = {"DefaultContainerRuntime": None}

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value=mock_plist_data
        ):
            result = self.handler.read_config()
            self.assertIsNone(result)

    def test_get_container_not_reachable_message_with_unknown_preference(self):
        """Test macOS error message when admin preference is unknown value"""
        with patch.object(self.handler, "read_config", return_value="unknown"):
            result = self.handler.get_container_not_reachable_message()
            expected = (
                "Running AWS SAM projects locally requires a container runtime. "
                "Do you have Docker or Finch installed and running?"
            )
            self.assertEqual(result, expected)


class TestLinuxHandler(unittest.TestCase):
    """Unit tests for LinuxHandler"""

    def setUp(self):
        self.handler = LinuxHandler()

    def test_read_config_not_implemented(self):
        """Test that Linux config reading returns None (not implemented)"""
        result = self.handler.read_config()
        self.assertIsNone(result)

    def test_get_finch_socket_path(self):
        """Test Linux Finch socket path"""
        result = self.handler.get_finch_socket_path()
        self.assertEqual(result, "unix:///var/run/finch.sock")

    def test_supports_finch(self):
        """Test that Linux supports Finch"""
        self.assertTrue(self.handler.supports_finch())

    def test_get_container_not_reachable_message_with_finch_preference(self):
        """Test Linux error message when admin preference is finch"""
        with patch.object(self.handler, "read_config", return_value="finch"):
            result = self.handler.get_container_not_reachable_message()
            self.assertEqual(
                result, "Running AWS SAM projects locally requires Finch. Do you have Finch installed and running?"
            )

    def test_get_container_not_reachable_message_with_docker_preference(self):
        """Test Linux error message when admin preference is docker"""
        with patch.object(self.handler, "read_config", return_value="docker"):
            result = self.handler.get_container_not_reachable_message()
            self.assertEqual(
                result, "Running AWS SAM projects locally requires Docker. Do you have Docker installed and running?"
            )

    def test_get_container_not_reachable_message_no_preference(self):
        """Test Linux error message when no admin preference is set"""
        with patch.object(self.handler, "read_config", return_value=None):
            result = self.handler.get_container_not_reachable_message()
            expected = (
                "Running AWS SAM projects locally requires a container runtime. "
                "Do you have Docker or Finch installed and running?"
            )
            self.assertEqual(result, expected)

    def test_get_container_not_reachable_message_with_unknown_preference(self):
        """Test Linux error message when admin preference is unknown value"""
        with patch.object(self.handler, "read_config", return_value="unknown"):
            result = self.handler.get_container_not_reachable_message()
            expected = (
                "Running AWS SAM projects locally requires a container runtime. "
                "Do you have Docker or Finch installed and running?"
            )
            self.assertEqual(result, expected)


class TestWindowsHandler(unittest.TestCase):
    """Unit tests for WindowsHandler"""

    def setUp(self):
        self.handler = WindowsHandler()

    def test_read_config_not_implemented(self):
        """Test that Windows config reading returns None (not implemented)"""
        result = self.handler.read_config()
        self.assertIsNone(result)

    def test_get_finch_socket_path_not_supported(self):
        """Test that Windows Finch socket path returns None (not supported)"""
        result = self.handler.get_finch_socket_path()
        self.assertIsNone(result)

    def test_supports_finch(self):
        """Test that Windows does not support Finch"""
        self.assertFalse(self.handler.supports_finch())

    def test_get_container_not_reachable_message(self):
        """Test Windows error message"""
        result = self.handler.get_container_not_reachable_message()
        expected = (
            "Running AWS SAM projects locally requires a container runtime. Do you have Docker installed and running?"
        )
        self.assertEqual(result, expected)


class TestGetPlatformHandler(unittest.TestCase):
    """Tests for get_platform_handler function"""

    @parameterized.expand(
        [
            ("Darwin", MacOSHandler),
            ("Linux", LinuxHandler),
            ("Windows", WindowsHandler),
        ]
    )
    @patch("samcli.local.docker.platform_config.platform.system")
    def test_returns_correct_handler(self, platform_name, expected_handler_class, mock_system):
        """Test that get_platform_handler returns the correct handler for each platform"""
        mock_system.return_value = platform_name

        handler = get_platform_handler()

        self.assertIsInstance(handler, expected_handler_class)
        mock_system.assert_called_once()

    @patch("samcli.local.docker.platform_config.platform.system")
    def test_returns_none_for_unsupported_platform(self, mock_system):
        """Test that get_platform_handler returns None for unsupported platforms"""
        mock_system.return_value = "FreeBSD"

        handler = get_platform_handler()

        self.assertIsNone(handler)
        mock_system.assert_called_once()


class TestMacOSHandlerIntegration(unittest.TestCase):
    """Integration tests for macOS platform handler"""

    @patch("samcli.local.docker.platform_config.platform.system")
    def test_happy_path(self, mock_system):
        """Test MacOS handler integration happy path"""
        mock_system.return_value = "Darwin"
        handler = get_platform_handler()

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value={"DefaultContainerRuntime": "finch"}
        ):
            config = handler.read_config()
            self.assertEqual(config, "finch")

    @parameterized.expand(
        [
            ("finch", "finch"),
            ("docker", "docker"),
            ("FINCH", "finch"),
            ("DOCKER", "docker"),
            ("Finch", "finch"),
            ("Docker", "docker"),
        ]
    )
    @patch("samcli.local.docker.platform_config.platform.system")
    def test_valid_values(self, container_runtime, expected, mock_system):
        """Test MacOS handler integration with valid container runtime values"""
        mock_system.return_value = "Darwin"
        handler = get_platform_handler()

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value={"DefaultContainerRuntime": container_runtime}
        ):
            config = handler.read_config()
            self.assertEqual(config, expected)

    @patch("samcli.local.docker.platform_config.platform.system")
    def test_sad_path_file_not_found(self, mock_system):
        """Test MacOS handler when config file doesn't exist"""
        mock_system.return_value = "Darwin"
        handler = get_platform_handler()

        with patch("os.path.exists", return_value=False), self.assertLogs(
            "samcli.local.docker.platform_config", level="DEBUG"
        ) as log_context:
            result = handler.read_config()
            self.assertIsNone(result)
            self.assertIn("Administrator config file not found on macOS", log_context.output[0])

    @parameterized.expand(
        [
            ("missing_key", {"SomeOtherKey": "value"}),
            ("empty_plist", {}),
        ]
    )
    @patch("samcli.local.docker.platform_config.platform.system")
    def test_sad_path_no_debug(self, scenario, plist_data, mock_system):
        """Test MacOS handler sad path scenarios that don't log debug messages"""
        mock_system.return_value = "Darwin"
        handler = get_platform_handler()

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", return_value=plist_data
        ):
            result = handler.read_config()
            self.assertIsNone(result)

    @parameterized.expand(
        [
            (FileNotFoundError, "Test file error"),
            (OSError, "Test OS error"),
            (plistlib.InvalidFileException, "Test plist error"),
        ]
    )
    @patch("samcli.local.docker.platform_config.platform.system")
    def test_exception_handling(self, exception_type, error_message, mock_system):
        """Test MacOS handler integration exception handling"""
        mock_system.return_value = "Darwin"
        handler = get_platform_handler()

        with patch("os.path.exists", return_value=True), patch("builtins.open", mock_open()), patch(
            "plistlib.load", side_effect=exception_type(error_message)
        ), self.assertLogs("samcli.local.docker.platform_config", level="DEBUG") as log_context:

            result = handler.read_config()
            self.assertIsNone(result)
            self.assertIn(f"Error reading macOS administrator config: {error_message}", log_context.output[0])


class TestLinuxHandlerIntegration(unittest.TestCase):
    """Integration tests for Linux platform handler"""

    @patch("samcli.local.docker.platform_config.platform.system")
    def test_integration(self, mock_system):
        """Test Linux handler integration through get_platform_handler"""
        mock_system.return_value = "Linux"

        handler = get_platform_handler()
        self.assertIsInstance(handler, LinuxHandler)

        # Linux handler returns None (not implemented yet)
        config = handler.read_config()
        self.assertIsNone(config)


class TestWindowsHandlerIntegration(unittest.TestCase):
    """Integration tests for Windows platform handler"""

    @patch("samcli.local.docker.platform_config.platform.system")
    def test_integration(self, mock_system):
        """Test Windows handler integration through get_platform_handler"""
        mock_system.return_value = "Windows"

        handler = get_platform_handler()
        self.assertIsInstance(handler, WindowsHandler)

        # Windows handler returns None (not implemented yet)
        config = handler.read_config()
        self.assertIsNone(config)


if __name__ == "__main__":
    unittest.main()
