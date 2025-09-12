"""
Manager for Lambda Function URL services
"""

import logging
import signal
import sys
from typing import Dict, Optional, Tuple, List, Any
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Event

from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.invoke_context import InvokeContext
from samcli.commands.local.lib.local_function_url_service import LocalFunctionUrlService
from samcli.commands.local.lib.port_manager import PortManager, PortExhaustedException
from samcli.lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)

class NoFunctionUrlsDefined(UserException):
    """Exception raised when no Function URLs are found in the template"""
    pass


class FunctionUrlManager:
    """
    Manages multiple Function URL services
    
    This class coordinates the startup and management of multiple
    Lambda Function URL services, each running on its own port.
    """
    
    def __init__(self, invoke_context: InvokeContext, host: str = "127.0.0.1",
                 port_range: Tuple[int, int] = (3001, 3010),
                 disable_authorizer: bool = False,
                 ssl_context: Optional[Tuple[str, str]] = None):
        """
        Initialize the Function URL manager
        
        Parameters
        ----------
        invoke_context : InvokeContext
            SAM CLI invoke context with Lambda runtime
        host : str
            Host to bind services to
        port_range : Tuple[int, int]
            Port range for auto-assignment (start, end)
        disable_authorizer : bool
            Whether to disable authorization checks
        ssl_context : Optional[Tuple[str, str]]
            SSL certificate and key file paths
        """
        self.invoke_context = invoke_context
        self.host = host
        self.port_range = port_range
        self.disable_authorizer = disable_authorizer
        self.ssl_context = ssl_context
        
        # Initialize port manager
        self.port_manager = PortManager(
            start_port=port_range[0],
            end_port=port_range[1]
        )
        
        # Service management
        self.services: Dict[str, LocalFunctionUrlService] = {}
        self.service_futures: Dict[str, Future] = {}
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="FunctionURL")
        self.shutdown_event = Event()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Extract Function URL configurations
        self.function_urls = self._extract_function_urls()
    
    def _extract_function_urls(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract Function URL configurations from the template
        
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Dictionary mapping function names to their Function URL configurations
        """
        function_urls = {}
        
        # Access the template through the invoke context
        if not self.invoke_context.stacks:
            return function_urls
        
        for stack in self.invoke_context.stacks:
            for name, resource in stack.resources.items():
                if resource.get("Type") == "AWS::Serverless::Function":
                    properties = resource.get("Properties", {})
                    if "FunctionUrlConfig" in properties:
                        url_config = properties["FunctionUrlConfig"]
                        function_urls[name] = {
                            "auth_type": url_config.get("AuthType", "AWS_IAM"),
                            "cors": url_config.get("Cors", {}),
                            "invoke_mode": url_config.get("InvokeMode", "BUFFERED")
                        }
                        LOG.debug(f"Found Function URL config for {name}: {url_config}")
        
        return function_urls
    
    def start_all(self):
        """
        Start all functions with Function URLs
        
        Raises
        ------
        NoFunctionUrlsDefined
            If no Function URLs are found in the template
        """
        if not self.function_urls:
            raise NoFunctionUrlsDefined(
                "No Lambda functions with Function URLs found in template.\n"
                "Add FunctionUrlConfig to your Lambda functions to use this feature.\n"
                "Example:\n"
                "  MyFunction:\n"
                "    Type: AWS::Serverless::Function\n"
                "    Properties:\n"
                "      ...\n"
                "      FunctionUrlConfig:\n"
                "        AuthType: NONE"
            )
        
        LOG.info(f"Starting {len(self.function_urls)} Function URL(s)...")
        
        # Start each function in a separate thread
        for func_name, func_config in self.function_urls.items():
            try:
                port = self.port_manager.allocate_port(func_name)
                future = self._start_function_service(func_name, func_config, port)
                self.service_futures[func_name] = future
            except PortExhaustedException as e:
                LOG.error(f"Failed to allocate port for {func_name}: {e}")
                self.shutdown()
                raise UserException(str(e)) from e
        
        # Print startup information only in debug mode
        if self.invoke_context._is_debugging:
            self._print_startup_info()
        
        # Wait for shutdown signal
        try:
            if self.invoke_context._is_debugging:
                LOG.info("Function URL services started. Press CTRL+C to stop.")
            self.shutdown_event.wait()
        except KeyboardInterrupt:
            LOG.info("Received interrupt signal")
        finally:
            self.shutdown()
    
    def start_function(self, function_name: str, port: Optional[int] = None):
        """
        Start a specific function with Function URL
        
        Parameters
        ----------
        function_name : str
            Name of the function to start
        port : Optional[int]
            Specific port to use (if None, auto-assign)
        
        Raises
        ------
        ValueError
            If function doesn't have a Function URL configuration
        """
        if function_name not in self.function_urls:
            available = ", ".join(self.function_urls.keys()) if self.function_urls else "none"
            raise ValueError(
                f"Function '{function_name}' does not have a Function URL configuration.\n"
                f"Available functions with Function URLs: {available}"
            )
        
        func_config = self.function_urls[function_name]
        
        try:
            assigned_port = self.port_manager.allocate_port(function_name, port)
        except (PortExhaustedException, ValueError) as e:
            raise UserException(str(e)) from e
        
        LOG.info(f"Starting Function URL for {function_name} on port {assigned_port}")
        
        # Start the service
        future = self._start_function_service(function_name, func_config, assigned_port)
        self.service_futures[function_name] = future
        
        # Print startup information for single function
        protocol = "https" if self.ssl_context else "http"
        url = f"{protocol}://{self.host}:{assigned_port}/"
        
        print("\n" + "="*60)
        print(f"Lambda Function URL: {function_name}")
        print(f"URL: {url}")
        print(f"AuthType: {func_config['auth_type']}")
        if func_config.get('cors'):
            print(f"CORS: Enabled")
        print("="*60)
        print("\nFunction URL service started. Press CTRL+C to stop.\n")
        
        # Wait for shutdown
        try:
            self.shutdown_event.wait()
        except KeyboardInterrupt:
            LOG.info("Received interrupt signal")
        finally:
            self.shutdown()
    
    def _start_function_service(self, function_name: str, 
                                func_config: Dict[str, Any], 
                                port: int) -> Future:
        """
        Start a single Function URL service
        
        Parameters
        ----------
        function_name : str
            Name of the function
        func_config : Dict[str, Any]
            Function URL configuration
        port : int
            Port to run the service on
        
        Returns
        -------
        Future
            Future representing the running service
        """
        # Create stderr stream writer
        stderr = StreamWriter(sys.stderr)
        
        # Create the service
        service = LocalFunctionUrlService(
            function_name=function_name,
            function_config=func_config,
            lambda_runner=self.invoke_context.local_lambda_runner,
            port=port,
            host=self.host,
            disable_authorizer=self.disable_authorizer,
            ssl_context=self.ssl_context,
            stderr=stderr,
            is_debugging=self.invoke_context._is_debugging
        )
        
        self.services[function_name] = service
        
        # Start service in executor
        def run_service():
            try:
                service.start()
                # Keep the thread alive while service is running
                while not self.shutdown_event.is_set():
                    self.shutdown_event.wait(1)
            except Exception as e:
                LOG.error(f"Error running Function URL service for {function_name}: {e}")
                raise
        
        return self.executor.submit(run_service)
    
    def _print_startup_info(self):
        """Print information about started services"""
        protocol = "https" if self.ssl_context else "http"
        
        print("\n" + "="*60)
        print("Lambda Function URLs - Local Testing")
        print("="*60)
        
        assignments = self.port_manager.get_assignments()
        for func_name, port in sorted(assignments.items()):
            url = f"{protocol}://{self.host}:{port}/"
            auth_type = self.function_urls[func_name]["auth_type"]
            cors_enabled = bool(self.function_urls[func_name].get("cors"))
            
            print(f"\n  {func_name}:")
            print(f"    URL: {url}")
            print(f"    AuthType: {auth_type}")
            if cors_enabled:
                print(f"    CORS: Enabled")
        
        print("\n" + "="*60)
        print("\nYou can now test your Lambda Function URLs locally.")
        print("Changes to your code will be reflected immediately.")
        print("\nPress CTRL+C to stop.\n")
        
        # Print example curl commands
        if assignments:
            first_func = next(iter(assignments.keys()))
            first_port = assignments[first_func]
            auth_type = self.function_urls[first_func]["auth_type"]
            
            print("Example commands:")
            print(f"  curl {protocol}://{self.host}:{first_port}/")
            
            if auth_type == "AWS_IAM":
                print(f"  # For IAM auth, add Authorization header:")
                print(f"  curl -H 'Authorization: AWS4-HMAC-SHA256 ...' {protocol}://{self.host}:{first_port}/")
            
            print()
    
    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals
        
        Parameters
        ----------
        signum : int
            Signal number
        frame : frame
            Current stack frame
        """
        LOG.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    def shutdown(self):
        """Shutdown all services and clean up resources"""
        LOG.info("Shutting down Function URL services...")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Cancel all futures
        for func_name, future in self.service_futures.items():
            if not future.done():
                LOG.debug(f"Cancelling service future for {func_name}")
                future.cancel()
        
        # Stop all services
        for func_name, service in self.services.items():
            try:
                LOG.debug(f"Stopping service for {func_name}")
                service.stop()
            except Exception as e:
                LOG.error(f"Error stopping service for {func_name}: {e}")
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
        # Release all ports
        self.port_manager.release_all()
        
        LOG.info("Function URL services stopped")
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all services
        
        Returns
        -------
        Dict[str, Dict[str, Any]]
            Status information for each service
        """
        status = {}
        
        for func_name, service in self.services.items():
            port = self.port_manager.get_port_for_function(func_name)
            future = self.service_futures.get(func_name)
            
            status[func_name] = {
                "port": port,
                "host": self.host,
                "running": future and not future.done() if future else False,
                "auth_type": self.function_urls[func_name]["auth_type"],
                "cors": bool(self.function_urls[func_name].get("cors"))
            }
        
        return status
