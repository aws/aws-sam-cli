"""
Unit tests for LocalFunctionUrlService
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from parameterized import parameterized

from samcli.commands.local.lib.local_function_url_service import LocalFunctionUrlService, PortExhaustedException
from samcli.commands.local.lib.exceptions import NoFunctionUrlsDefined


class TestLocalFunctionUrlService(unittest.TestCase):
    """Test the LocalFunctionUrlService class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock InvokeContext
        self.invoke_context = Mock()
        self.invoke_context.local_lambda_runner = Mock()
        self.invoke_context.stderr = Mock()
        self.invoke_context.stacks = []

        # Mock the port range
        self.port_range = (3001, 3010)
        self.host = "127.0.0.1"

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_init_no_function_urls(self, mock_provider_class):
        """Test initialization when no functions have Function URLs"""
        # Setup
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = []  # No functions

        # Execute and verify
        with self.assertRaises(NoFunctionUrlsDefined):
            LocalFunctionUrlService(
                lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
            )

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_init_with_function_urls(self, mock_provider_class):
        """Test initialization with functions that have Function URLs"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE", "Cors": {"AllowOrigins": ["*"]}}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        # Execute
        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Verify
        self.assertEqual(service.host, self.host)
        self.assertEqual(service.port_range, self.port_range)
        self.assertIn("TestFunction", service.function_urls)
        self.assertEqual(service.function_urls["TestFunction"]["auth_type"], "NONE")

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_discover_function_urls(self, mock_provider_class):
        """Test discovering functions with Function URL configurations"""
        # Setup
        func1 = Mock()
        func1.name = "Function1"
        func1.function_url_config = {"AuthType": "AWS_IAM"}

        func2 = Mock()
        func2.name = "Function2"
        func2.function_url_config = {"AuthType": "NONE", "InvokeMode": "RESPONSE_STREAM"}

        func3 = Mock()
        func3.name = "Function3"
        func3.function_url_config = None  # No Function URL

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [func1, func2, func3]

        # Execute
        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Verify
        self.assertEqual(len(service.function_urls), 2)
        self.assertIn("Function1", service.function_urls)
        self.assertIn("Function2", service.function_urls)
        self.assertNotIn("Function3", service.function_urls)
        self.assertEqual(service.function_urls["Function1"]["auth_type"], "AWS_IAM")
        self.assertEqual(service.function_urls["Function2"]["invoke_mode"], "RESPONSE_STREAM")

    @patch("samcli.commands.local.lib.local_function_url_service.find_free_port")
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_allocate_port(self, mock_provider_class, mock_find_free_port):
        """Test port allocation using find_free_port utility"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Mock find_free_port to return a port
        mock_find_free_port.return_value = 3001

        # Execute
        port = service._allocate_port()

        # Verify
        self.assertEqual(port, 3001)
        self.assertIn(3001, service._used_ports)
        mock_find_free_port.assert_called()

    @patch("samcli.commands.local.lib.local_function_url_service.find_free_port")
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_allocate_port_exhausted(self, mock_provider_class, mock_find_free_port):
        """Test port allocation when all ports are used"""
        # Setup
        from samcli.local.docker.exceptions import NoFreePortsError
        
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=(3001, 3002), host=self.host  # Only 2 ports
        )

        # Mock find_free_port to raise NoFreePortsError (no ports available)
        mock_find_free_port.side_effect = NoFreePortsError("No free ports")

        # Execute and verify
        with self.assertRaises(PortExhaustedException):
            service._allocate_port()

    @patch("samcli.commands.local.lib.local_function_url_service.FunctionUrlHandler")
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_start_function_service(self, mock_provider_class, mock_handler_class):
        """Test starting an individual function service"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Execute
        result = service._start_function_service(func_name="TestFunction", func_config={"auth_type": "NONE"}, port=3001)

        # Verify
        self.assertEqual(result, mock_handler)
        mock_handler_class.assert_called_once_with(
            function_name="TestFunction",
            function_config={"auth_type": "NONE"},
            local_lambda_runner=self.invoke_context.local_lambda_runner,
            port=3001,
            host="127.0.0.1",
            disable_authorizer=False,
            stderr=self.invoke_context.stderr,
            ssl_context=None,
        )

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_start_with_no_urls(self, mock_provider_class):
        """Test starting service when no Function URLs are configured"""
        # Setup
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = []  # No functions

        # Execute and verify - initialization itself should raise NoFunctionUrlsDefined
        with self.assertRaises(NoFunctionUrlsDefined):
            LocalFunctionUrlService(
                lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
            )

    @patch("samcli.commands.local.lib.local_function_url_service.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.local_function_url_service.FunctionUrlHandler")
    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_start_function_specific(self, mock_provider_class, mock_handler_class, mock_executor_class):
        """Test starting a specific function using consolidated start() method"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        mock_handler = Mock()
        mock_handler_class.return_value = mock_handler

        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Mock the shutdown event and wait_for_service
        with patch.object(service._shutdown_event, "wait"), patch.object(service, "_wait_for_service", return_value=True):
            service._shutdown_event.wait.side_effect = KeyboardInterrupt()

            # Execute - using consolidated start() method with function_name parameter
            try:
                service.start(function_name="TestFunction", port=3001)
            except KeyboardInterrupt:
                pass

            # Verify
            mock_handler.start.assert_called_once()
            self.assertIn("TestFunction", service.services)

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_start_function_not_found(self, mock_provider_class):
        """Test starting a function that doesn't have Function URL using consolidated start() method"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Execute and verify - using consolidated start() method with function_name parameter
        with self.assertRaises(NoFunctionUrlsDefined):
            service.start(function_name="NonExistentFunction", port=3001)

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_get_service_status(self, mock_provider_class):
        """Test getting service status"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Add a mock service
        mock_service = Mock()
        mock_service.port = 3001
        service.services["TestFunction"] = mock_service

        # Execute
        status = service.get_service_status()

        # Verify
        self.assertIn("TestFunction", status)
        self.assertEqual(status["TestFunction"]["port"], 3001)
        self.assertEqual(status["TestFunction"]["auth_type"], "NONE")

    @patch("samcli.lib.providers.sam_function_provider.SamFunctionProvider")
    def test_shutdown_services(self, mock_provider_class):
        """Test shutting down services"""
        # Setup
        mock_function = Mock()
        mock_function.name = "TestFunction"
        mock_function.function_url_config = {"AuthType": "NONE"}

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.get_all.return_value = [mock_function]

        service = LocalFunctionUrlService(
            lambda_invoke_context=self.invoke_context, port_range=self.port_range, host=self.host
        )

        # Add mock services
        mock_service1 = Mock()
        mock_service2 = Mock()
        service.services = {"Function1": mock_service1, "Function2": mock_service2}

        # Add mock executor
        mock_executor = Mock()
        service.executor = mock_executor

        # Execute
        service._shutdown_services()

        # Verify
        mock_service1.stop.assert_called_once()
        mock_service2.stop.assert_called_once()
        mock_executor.shutdown.assert_called_once_with(wait=True)


if __name__ == "__main__":
    unittest.main()
