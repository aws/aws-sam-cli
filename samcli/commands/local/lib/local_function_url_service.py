"""
Local Lambda Function URL Service implementation
"""

import logging
import signal
import socket
import sys
import time
from typing import Dict, Optional, Tuple, List, Any
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Event

from samcli.commands.local.cli_common.invoke_context import InvokeContext
from samcli.commands.local.lib.exceptions import NoFunctionUrlsDefined
from samcli.commands.local.lib.function_url_handler import FunctionUrlHandler
from samcli.lib.utils.stream_writer import StreamWriter

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
    
    def __init__(self, lambda_invoke_context: InvokeContext,
                 port_range: Tuple[int, int] = (3001, 3010),
                 host: str = "127.0.0.1",
                 disable_authorizer: bool = False):
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
        self._used_ports = set()
        self._port_start, self._port_end = port_range
        
        # Service management
        self.function_urls = {}
        self.services = {}
        self.executor = None
        self.futures = {}
        self._shutdown_event = Event()
        
        # Discover function URLs
        self._discover_function_urls()
    
    def _discover_function_urls(self):
        """Discover functions with FunctionUrlConfig in the template"""
        self.function_urls = {}
        
        # Use the function provider to get all functions
        from samcli.lib.providers.sam_function_provider import SamFunctionProvider
        
        function_provider = SamFunctionProvider(
            stacks=self.invoke_context.stacks,
            use_raw_codeuri=True
        )
        
        # Get all functions and check for Function URL configs
        for function in function_provider.get_all():
            if function.function_url_config:
                # Extract the configuration
                config = function.function_url_config
                self.function_urls[function.name] = {
                    "auth_type": config.get("AuthType", "AWS_IAM"),
                    "cors": config.get("Cors", {}),
                    "invoke_mode": config.get("InvokeMode", "BUFFERED")
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
        Allocate next available port in range
        
        Returns
        -------
        int
            An available port number
            
        Raises
        ------
        PortExhaustedException
            When no ports are available in the specified range
        """
        for port in range(self._port_start, self._port_end + 1):
            if port not in self._used_ports:
                # Actually check if the port is available by trying to bind to it
                if self._is_port_available(port):
                    self._used_ports.add(port)
                    return port
        raise PortExhaustedException(f"No available ports in range {self._port_start}-{self._port_end}")
    
    def _is_port_available(self, port: int) -> bool:
        """
        Check if a port is available by attempting to bind to it
        
        Parameters
        ----------
        port : int
            Port number to check
            
        Returns
        -------
        bool
            True if port is available, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, port))
                return True
        except OSError:
            LOG.debug(f"Port {port} is already in use")
            return False
    
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
            ssl_context=None
        )
        return service
    
    def start(self):
        """
        Start the Function URL services. This method will block until stopped.
        """
        if not self.function_urls:
            raise NoFunctionUrlsDefined("No Function URLs found to start")
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            LOG.info("Received interrupt signal. Shutting down...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start services
        self.executor = ThreadPoolExecutor(max_workers=len(self.function_urls))
        
        try:
            # Start each function service
            for func_name, func_config in self.function_urls.items():
                port = self._allocate_port()
                service = self._start_function_service(func_name, func_config, port)
                self.services[func_name] = service
                
                # Start the service (this runs Flask in a thread)
                service.start()
                
                # Wait for the service to be ready
                if not self._wait_for_service(port):
                    LOG.warning(f"Service for {func_name} on port {port} did not start properly")
            
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
        Start all Function URL services. Alias for start() method.
        """
        return self.start()
    
    def start_function(self, function_name: str, port: int):
        """
        Start a specific function URL service on the given port.
        
        Args:
            function_name: Name of the function to start
            port: Port to bind the service to
        """
        if function_name not in self.function_urls:
            raise NoFunctionUrlsDefined(f"Function {function_name} does not have a Function URL configured")
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            LOG.info("Received interrupt signal. Shutting down...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        function_url_config = self.function_urls[function_name]
        service = self._start_function_service(function_name, function_url_config, port)
        self.services[function_name] = service
        
        # Start the service (this runs Flask in a thread)
        service.start()
        
        # Start service in thread
        self.executor = ThreadPoolExecutor(max_workers=1)
        
        # Print startup info for single function
        url = f"http://{self.host}:{port}/"
        auth_type = function_url_config["auth_type"]
        cors_enabled = bool(function_url_config.get("cors"))
        
        print("\\n" + "="*60)
        print("SAM Local Function URL")
        print("="*60)
        print(f"\\n  {function_name}:")
        print(f"    URL: {url}")
        print(f"    Auth: {auth_type}")
        print(f"    CORS: {'Enabled' if cors_enabled else 'Disabled'}")
        print("\\n" + "="*60)
        
        try:
            # Wait for shutdown signal
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            LOG.info("Received keyboard interrupt")
        finally:
            self._shutdown_services()
    
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
        print("\\n" + "="*60)
        print("SAM Local Function URLs")
        print("="*60)
        
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
                    print(f"    CORS: Enabled")
        
        print("\\n" + "="*60, file=sys.stderr)
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
                "cors": bool(self.function_urls[func_name].get("cors"))
            }
        
        return status
