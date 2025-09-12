"""
Unit tests for FunctionUrlManager
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from parameterized import parameterized

from samcli.commands.local.lib.function_url_manager import (
    FunctionUrlManager,
    NoFunctionUrlsDefined,
)


class TestFunctionUrlManager(unittest.TestCase):
    def setUp(self):
        self.invoke_context_mock = Mock()
        self.invoke_context_mock.function_name = "TestFunction"
        self.invoke_context_mock.local_lambda_runner = Mock()
        self.invoke_context_mock.stderr = Mock()
        self.invoke_context_mock._is_debugging = False
        
        # Mock stacks with proper resources dictionary
        stack_mock = Mock()
        stack_mock.resources = {
            "Function1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionUrlConfig": {
                        "AuthType": "NONE",
                        "Cors": {}
                    }
                }
            },
            "Function2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionUrlConfig": {
                        "AuthType": "AWS_IAM",
                        "Cors": {
                            "AllowOrigins": ["*"]
                        }
                    }
                }
            },
            "Function3": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # No FunctionUrlConfig
                }
            }
        }
        self.invoke_context_mock.stacks = [stack_mock]
        
        self.host = "127.0.0.1"
        self.port_range = (3001, 3010)
        self.disable_authorizer = False
        self.ssl_context = None

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_init_creates_port_manager(self, service_mock, port_manager_mock):
        """Test that FunctionUrlManager initializes PortManager correctly"""
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        port_manager_mock.assert_called_once_with(
            start_port=3001,
            end_port=3010
        )
        self.assertIsNotNone(manager.port_manager)

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_extract_function_url_configs(self, service_mock, port_manager_mock):
        """Test extraction of Function URL configurations from stacks"""
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        configs = manager._extract_function_urls()
        
        self.assertEqual(len(configs), 2)
        self.assertIn("Function1", configs)
        self.assertIn("Function2", configs)
        self.assertNotIn("Function3", configs)  # No FunctionUrlConfig
        self.assertEqual(configs["Function1"]["auth_type"], "NONE")
        self.assertEqual(configs["Function2"]["auth_type"], "AWS_IAM")

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_extract_function_url_configs_no_stacks(self, service_mock, port_manager_mock):
        """Test extraction when no stacks are present"""
        self.invoke_context_mock.stacks = []
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        configs = manager._extract_function_urls()
        self.assertEqual(configs, {})

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_start_all_with_no_function_urls(self, service_mock, port_manager_mock):
        """Test start_all raises exception when no Function URLs are defined"""
        # Mock stack with no Function URLs
        stack_mock = Mock()
        stack_mock.resources = {
            "Function1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {}  # No FunctionUrlConfig
            }
        }
        self.invoke_context_mock.stacks = [stack_mock]
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        with self.assertRaises(NoFunctionUrlsDefined) as context:
            manager.start_all()
        
        self.assertIn("No Lambda functions with Function URLs", str(context.exception))

    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_start_all_starts_services(self, service_mock, port_manager_mock, executor_mock, stream_writer_mock):
        """Test start_all starts services for all functions with URLs"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.side_effect = [3001, 3002]
        
        service_instance = Mock()
        service_mock.return_value = service_instance
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        future_mock = Mock()
        executor_instance.submit.return_value = future_mock
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        # Mock the shutdown event to exit immediately
        manager.shutdown_event.set()
        
        manager.start_all()
        
        # Verify services were created for both functions with URLs
        self.assertEqual(service_mock.call_count, 2)
        
        # Verify executor.submit was called for each service
        self.assertEqual(executor_instance.submit.call_count, 2)
        
        # Verify ports were allocated
        self.assertEqual(port_manager_instance.allocate_port.call_count, 2)

    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_start_function_with_specific_port(self, service_mock, port_manager_mock, executor_mock, stream_writer_mock):
        """Test starting a specific function with a specific port"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.return_value = 3005
        
        service_instance = Mock()
        service_mock.return_value = service_instance
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        future_mock = Mock()
        executor_instance.submit.return_value = future_mock
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        # Mock the shutdown event to exit immediately
        manager.shutdown_event.set()
        
        manager.start_function("Function1", 3005)
        
        # Verify port allocation was called with preferred port
        port_manager_instance.allocate_port.assert_called_once_with("Function1", 3005)
        
        # Verify service was created
        service_mock.assert_called_once()
        
        # Verify executor.submit was called
        executor_instance.submit.assert_called_once()

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_start_function_not_found(self, service_mock, port_manager_mock):
        """Test starting a function that doesn't have Function URL configured"""
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        with self.assertRaises(ValueError) as context:
            manager.start_function("NonExistentFunction", None)
        
        self.assertIn("Function 'NonExistentFunction' does not have", str(context.exception))

    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_stop_all_services(self, service_mock, port_manager_mock, executor_mock, stream_writer_mock):
        """Test stopping all services"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.side_effect = [3001, 3002]
        
        # Create separate service instances for each call
        service_instance1 = Mock()
        service_instance2 = Mock()
        service_mock.side_effect = [service_instance1, service_instance2]
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        future_mock = Mock()
        future_mock.done.return_value = False
        executor_instance.submit.return_value = future_mock
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        # Manually add services without starting (to avoid automatic shutdown)
        manager.services["Function1"] = service_instance1
        manager.services["Function2"] = service_instance2
        manager.service_futures["Function1"] = future_mock
        manager.service_futures["Function2"] = future_mock
        
        # Now stop them
        manager.shutdown()
        
        # Verify both services were stopped
        service_instance1.stop.assert_called_once()
        service_instance2.stop.assert_called_once()
        
        # Verify all ports were released
        port_manager_instance.release_all.assert_called_once()
        
        # Verify executor was shutdown
        executor_instance.shutdown.assert_called_once_with(wait=False)

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_wait_for_services(self, service_mock, port_manager_mock):
        """Test waiting for services to complete"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        # Test that shutdown_event.wait() is called
        with patch.object(manager.shutdown_event, 'wait') as wait_mock:
            manager.shutdown_event.set()  # Set to exit immediately
            try:
                manager.start_all()
            except NoFunctionUrlsDefined:
                pass  # Expected since we're not setting up services
            
            # Verify wait was called
            wait_mock.assert_called()

    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_disable_authorizer_passed_to_services(self, service_mock, port_manager_mock, executor_mock, stream_writer_mock):
        """Test that disable_authorizer flag is passed to services"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.return_value = 3001
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        
        self.disable_authorizer = True
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        manager.shutdown_event.set()
        manager.start_function("Function2", None)
        
        # Verify service was created with disable_authorizer=True
        service_mock.assert_called_once()
        call_kwargs = service_mock.call_args.kwargs
        self.assertTrue(call_kwargs["disable_authorizer"])

    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_ssl_context_passed_to_services(self, service_mock, port_manager_mock, executor_mock, stream_writer_mock):
        """Test that SSL context is passed to services"""
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.return_value = 3001
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        
        ssl_context_mock = Mock()
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            ssl_context_mock,
        )
        
        manager.shutdown_event.set()
        manager.start_function("Function1", None)
        
        # Verify service was created with SSL context
        service_mock.assert_called_once()
        call_kwargs = service_mock.call_args.kwargs
        self.assertEqual(call_kwargs["ssl_context"], ssl_context_mock)

    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_port_allocation_failure(self, service_mock, port_manager_mock):
        """Test handling of port allocation failure"""
        from samcli.commands.local.lib.port_manager import PortExhaustedException
        
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.side_effect = PortExhaustedException("All ports exhausted")
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            self.disable_authorizer,
            self.ssl_context,
        )
        
        from samcli.commands.exceptions import UserException
        with self.assertRaises(UserException) as context:
            manager.start_function("Function1", None)
        
        self.assertIn("All ports exhausted", str(context.exception))

    @parameterized.expand([
        ("NONE", False, False),  # NONE auth, no disable flag
        ("NONE", True, True),    # NONE auth, with disable flag
        ("AWS_IAM", False, False),  # IAM auth, no disable flag
        ("AWS_IAM", True, True),    # IAM auth, with disable flag
    ])
    @patch("samcli.commands.local.lib.function_url_manager.StreamWriter")
    @patch("samcli.commands.local.lib.function_url_manager.ThreadPoolExecutor")
    @patch("samcli.commands.local.lib.function_url_manager.PortManager")
    @patch("samcli.commands.local.lib.function_url_manager.LocalFunctionUrlService")
    def test_auth_type_and_disable_flag_combinations(
        self, auth_type, disable_flag, expected_disable, service_mock, port_manager_mock, executor_mock, stream_writer_mock
    ):
        """Test various combinations of auth type and disable_authorizer flag"""
        # Create a custom stack with the specific auth type
        stack_mock = Mock()
        stack_mock.resources = {
            "TestFunc": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionUrlConfig": {
                        "AuthType": auth_type,
                        "Cors": {}
                    }
                }
            }
        }
        self.invoke_context_mock.stacks = [stack_mock]
        
        port_manager_instance = Mock()
        port_manager_mock.return_value = port_manager_instance
        port_manager_instance.allocate_port.return_value = 3001
        
        executor_instance = Mock()
        executor_mock.return_value = executor_instance
        
        manager = FunctionUrlManager(
            self.invoke_context_mock,
            self.host,
            self.port_range,
            disable_flag,
            self.ssl_context,
        )
        
        manager.shutdown_event.set()
        manager.start_function("TestFunc", None)
        
        # Verify the disable_authorizer value passed to service
        call_kwargs = service_mock.call_args.kwargs
        self.assertEqual(call_kwargs["disable_authorizer"], expected_disable)


if __name__ == "__main__":
    unittest.main()
