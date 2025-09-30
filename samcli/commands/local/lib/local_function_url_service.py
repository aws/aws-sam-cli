"""
Local Lambda Function URL Service implementation
"""

import logging
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any, Dict, Optional, Set, Tuple

from samcli.commands.local.cli_common.invoke_context import InvokeContext
from samcli.commands.local.lib.exceptions import NoFunctionUrlsDefined
from samcli.commands.local.lib.function_url_handler import FunctionUrlHandler
from samcli.local.docker.utils import find_free_port

LOG = logging.getLogger(__name__)


class PortExhaustedException(Exception):
    """Exception raised when no ports are available in the specified range"""

    pass


class LocalFunctionUrlService:
    """
    Local service for Lambda Function URLs following SAM CLI patterns

    This service coordinates the startup and management of multiple
    Lambda Function URL services, each running on its own port.
    """

    def __init__(
        self,
        lambda_invoke_context: InvokeContext,
        port_range: Tuple[int, int] = (3001, 3010),
        host: str = "127.0.0.1",
        disable_authorizer: bool = False,
    ):
        """
        Initialize the Function URL service

        Parameters
        ----------
        lambda_invoke_context : InvokeContext
            SAM CLI invoke context with Lambda runtime
        port_range : Tuple[int, int]
            Port range for auto-assignment (start, end)
        host : str
            Host to bind services to
        disable_authorizer : bool
            Whether to disable authorization checks
        """
        self.invoke_context = lambda_invoke_context
        self.host = host
        self.port_range = port_range
        self.disable_authorizer = disable_authorizer

        # Port management
        self._used_ports: Set[int] = set()
        self._port_start, self._port_end = port_range

        # Service management
        self.function_urls: Dict[str, Dict[str, Any]] = {}
        self.services: Dict[str, FunctionUrlHandler] = {}
        self.executor: Optional[ThreadPoolExecutor] = None
        self.futures: Dict[str, Any] = {}
        self._shutdown_event = Event()

        # Discover function URLs
        self._discover_function_urls()

    def _discover_function_urls(self):
        """Discover functions with FunctionUrlConfig in the template"""
        self.function_urls = {}

        # Use the function provider to get all functions
        from samcli.lib.providers.sam_function_provider import SamFunctionProvider

        function_provider = SamFunctionProvider(stacks=self.invoke_context.stacks, use_raw_codeuri=True)

        # Get all functions and check for Function URL configs
        for function in function_provider.get_all():
            if function.function_url_config:
                # Extract the configuration
                config = function.function_url_config
                self.function_urls[function.name] = {
                    "auth_type": config.get("AuthType", "AWS_IAM"),
                    "cors": config.get("Cors", {}),
                    "invoke_mode": config.get("InvokeMode", "BUFFERED"),
                }

        if not self.function_urls:
            raise NoFunctionUrlsDefined(
                "No Lambda functions with FunctionUrlConfig found in template.\\n"
                "Add FunctionUrlConfig to your Lambda functions to use this feature.\\n"
                "Example:\\n"
                "  MyFunction:\\n"
                "    Type: AWS::Serverless::Function\\n"
                "    Properties:\\n"
                "      FunctionUrlConfig:\\n"
                "        AuthType: NONE"
            )

    def _allocate_port(self) -> int:
        """
        Allocate next available port in range using existing find_free_port utility

        Returns
        -------
        int
            An available port number

        Raises
        ------
        PortExhaustedException
            When no ports are available in the specified range
        """
        # Try to find a free port in the specified range
        # find_free_port signature: (network_interface: str, start: int, end: int)
        # find_free_port raises NoFreePortsError if no ports available
        try:
            port = find_free_port(network_interface=self.host, start=self._port_start, end=self._port_end)
            if port and port not in self._used_ports:
                self._used_ports.add(port)
                return port
        except Exception:
            # NoFreePortsError or any other exception
            raise PortExhaustedException(f"No available ports in range {self._port_start}-{self._port_end}")
        
        # If port was None or already used, raise exception
        raise PortExhaustedException(f"No available ports in range {self._port_start}-{self._port_end}")

    def _start_function_service(self, func_name: str, func_config: Dict, port: int) -> FunctionUrlHandler:
        """Start individual function URL service"""
        service = FunctionUrlHandler(
            function_name=func_name,
            function_config=func_config,
            local_lambda_runner=self.invoke_context.local_lambda_runner,
            port=port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            stderr=self.invoke_context.stderr,
            ssl_context=None,
        )
        return service

    def start(self, function_name: Optional[str] = None, port: Optional[int] = None):
        """
        Start the Function URL services. This method will block until stopped.
        
        Parameters
        ----------
        function_name : Optional[str]
            If specified, only start this function. If None, start all functions.
        port : Optional[int]
            If specified (with function_name), use this port. Otherwise auto-allocate.
        """
        if not self.function_urls:
            raise NoFunctionUrlsDefined("No Function URLs found to start")

        # Determine which functions to start
        if function_name:
            if function_name not in self.function_urls:
                raise NoFunctionUrlsDefined(f"Function {function_name} does not have a Function URL configured")
            functions_to_start = {function_name: self.function_urls[function_name]}
        else:
            functions_to_start = self.function_urls

        # Start services
        self.executor = ThreadPoolExecutor(max_workers=len(functions_to_start))

        try:
            # Start each function service
            for func_name, func_config in functions_to_start.items():
                # Use specified port for single function, otherwise allocate
                service_port = port if function_name and port else self._allocate_port()
                service = self._start_function_service(func_name, func_config, service_port)
                self.services[func_name] = service

                # Start the service (this runs Flask in a thread)
                service.start()

                # Wait for the service to be ready
                if not self._wait_for_service(service_port):
                    LOG.warning(f"Service for {func_name} on port {service_port} did not start properly")

            # Print startup info
            self._print_startup_info()

            # Wait for shutdown signal
            self._shutdown_event.wait()

        except KeyboardInterrupt:
            LOG.info("Received keyboard interrupt")
        finally:
            self._shutdown_services()

    def start_all(self):
        """
        Start all Function URL services. Alias for start() without parameters.
        """
        return self.start()

    def _wait_for_service(self, port: int, timeout: int = 5) -> bool:
        """
        Wait for a service to be ready on the specified port

        Parameters
        ----------
        port : int
            Port to check
        timeout : int
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if service is ready, False otherwise
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((self.host, port))
                    if result == 0:
                        # Give Flask a bit more time to fully initialize
                        time.sleep(0.2)
                        return True
            except socket.error:
                pass
            time.sleep(0.1)
        return False

    def _print_startup_info(self):
        """Print service startup information"""
        print("\\n" + "=" * 60)
        print("SAM Local Function URLs")
        print("=" * 60)

        for func_name, func_config in self.function_urls.items():
            service = self.services.get(func_name)
            if service:
                port = service.port
                url = f"http://{self.host}:{port}/"
                auth_type = func_config["auth_type"]
                cors_enabled = bool(func_config.get("cors"))

                print(f"\\n  {func_name}:")
                print(f"    URL: {url}")
                print(f"    AuthType: {auth_type}")
                if cors_enabled:
                    print("    CORS: Enabled")

        print("\\n" + "=" * 60, file=sys.stderr)
        print("Function URL services started. Press CTRL+C to stop.\\n", file=sys.stderr)

    def _shutdown_services(self):
        """Shutdown all running services"""
        LOG.info("Shutting down Function URL services...")

        # Stop all services
        for service in self.services.values():
            try:
                service.stop()
            except Exception as e:
                LOG.warning(f"Error stopping service: {e}")

        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)

        LOG.info("All services stopped")

    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all running services"""
        status = {}
        for func_name in self.function_urls:
            service = self.services.get(func_name)
            future = self.futures.get(func_name)

            status[func_name] = {
                "port": service.port if service else None,
                "running": future and not future.done() if future else False,
                "auth_type": self.function_urls[func_name]["auth_type"],
                "cors": bool(self.function_urls[func_name].get("cors")),
            }

        return status
