"""
Port management for Lambda Function URLs
"""

import socket
import logging
from typing import Dict, Optional, Set
from threading import Lock

LOG = logging.getLogger(__name__)


class PortExhaustedException(Exception):
    """Exception raised when no ports are available in the specified range"""
    pass


class PortManager:
    """
    Manages port allocation for Function URL endpoints
    
    This class provides thread-safe port allocation and management
    for multiple Lambda Function URL services running locally.
    """
    
    DEFAULT_START_PORT = 3001
    DEFAULT_END_PORT = 3010
    
    def __init__(self, start_port: int = DEFAULT_START_PORT, 
                 end_port: int = DEFAULT_END_PORT):
        """
        Initialize the port manager
        
        Parameters
        ----------
        start_port : int
            Starting port number for allocation range
        end_port : int
            Ending port number for allocation range
        """
        self.start_port = start_port
        self.end_port = end_port
        self.assigned_ports: Dict[str, int] = {}
        self.reserved_ports: Set[int] = set()
        self._lock = Lock()
        
        if start_port > end_port:
            raise ValueError(f"Start port {start_port} must be less than or equal to end port {end_port}")
        
        if start_port < 1024:
            LOG.warning(f"Using privileged port range (< 1024). Port {start_port} may require elevated permissions.")
        
        if end_port > 65535:
            raise ValueError(f"End port {end_port} exceeds maximum port number 65535")
    
    def allocate_port(self, function_name: str, 
                     preferred_port: Optional[int] = None) -> int:
        """
        Allocate a port for a function
        
        Parameters
        ----------
        function_name : str
            Name of the function to allocate port for
        preferred_port : Optional[int]
            Preferred port number if available
        
        Returns
        -------
        int
            Allocated port number
        
        Raises
        ------
        PortExhaustedException
            If no ports are available in the range
        ValueError
            If preferred port is outside the configured range
        """
        with self._lock:
            # Check if function already has a port assigned
            if function_name in self.assigned_ports:
                existing_port = self.assigned_ports[function_name]
                LOG.debug(f"Function {function_name} already assigned port {existing_port}")
                return existing_port
            
            # Try to use preferred port if specified
            if preferred_port is not None:
                if preferred_port < self.start_port or preferred_port > self.end_port:
                    raise ValueError(
                        f"Preferred port {preferred_port} is outside configured range "
                        f"{self.start_port}-{self.end_port}"
                    )
                
                if self._is_port_available(preferred_port):
                    self.assigned_ports[function_name] = preferred_port
                    self.reserved_ports.add(preferred_port)
                    LOG.info(f"Allocated preferred port {preferred_port} to function {function_name}")
                    return preferred_port
                else:
                    LOG.warning(f"Preferred port {preferred_port} is not available for {function_name}")
            
            # Auto-assign from range
            port = self._find_available_port()
            if port:
                self.assigned_ports[function_name] = port
                self.reserved_ports.add(port)
                LOG.info(f"Allocated port {port} to function {function_name}")
                return port
            
            # No ports available
            assigned_list = ", ".join(f"{fn}:{p}" for fn, p in self.assigned_ports.items())
            raise PortExhaustedException(
                f"No available ports in range {self.start_port}-{self.end_port}. "
                f"Currently assigned: {assigned_list}"
            )
    
    def _is_port_available(self, port: int) -> bool:
        """
        Check if a port is available for binding
        
        Parameters
        ----------
        port : int
            Port number to check
        
        Returns
        -------
        bool
            True if port is available, False otherwise
        """
        # Check if already assigned or reserved
        if port in self.reserved_ports:
            return False
        
        if port in self.assigned_ports.values():
            return False
        
        # Try to bind to the port to check availability
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('', port))
                return True
        except OSError as e:
            LOG.debug(f"Port {port} is not available: {e}")
            return False
    
    def _find_available_port(self) -> Optional[int]:
        """
        Find the next available port in the configured range
        
        Returns
        -------
        Optional[int]
            Available port number or None if no ports available
        """
        for port in range(self.start_port, self.end_port + 1):
            if self._is_port_available(port):
                return port
        return None
    
    def release_port(self, function_name: str) -> Optional[int]:
        """
        Release a port assignment for a function
        
        Parameters
        ----------
        function_name : str
            Name of the function to release port for
        
        Returns
        -------
        Optional[int]
            Released port number or None if function had no port assigned
        """
        with self._lock:
            if function_name in self.assigned_ports:
                port = self.assigned_ports.pop(function_name)
                self.reserved_ports.discard(port)
                LOG.info(f"Released port {port} from function {function_name}")
                return port
            return None
    
    def release_all(self):
        """Release all port assignments"""
        with self._lock:
            released = list(self.assigned_ports.items())
            self.assigned_ports.clear()
            self.reserved_ports.clear()
            
            for function_name, port in released:
                LOG.info(f"Released port {port} from function {function_name}")
    
    def get_assignments(self) -> Dict[str, int]:
        """
        Get current port assignments
        
        Returns
        -------
        Dict[str, int]
            Dictionary mapping function names to their assigned ports
        """
        with self._lock:
            return self.assigned_ports.copy()
    
    def get_port_for_function(self, function_name: str) -> Optional[int]:
        """
        Get the assigned port for a specific function
        
        Parameters
        ----------
        function_name : str
            Name of the function
        
        Returns
        -------
        Optional[int]
            Assigned port number or None if not assigned
        """
        with self._lock:
            return self.assigned_ports.get(function_name)
    
    def is_port_in_range(self, port: int) -> bool:
        """
        Check if a port is within the configured range
        
        Parameters
        ----------
        port : int
            Port number to check
        
        Returns
        -------
        bool
            True if port is in range, False otherwise
        """
        return self.start_port <= port <= self.end_port
    
    def get_available_count(self) -> int:
        """
        Get the number of available ports remaining
        
        Returns
        -------
        int
            Number of available ports
        """
        with self._lock:
            total_ports = self.end_port - self.start_port + 1
            used_ports = len(self.assigned_ports)
            return total_ports - used_ports
    
    def __str__(self) -> str:
        """String representation of port manager state"""
        with self._lock:
            total_ports = self.end_port - self.start_port + 1
            used_ports = len(self.assigned_ports)
            available = total_ports - used_ports
            return (
                f"PortManager(range={self.start_port}-{self.end_port}, "
                f"assigned={used_ports}, "
                f"available={available})"
            )
    
    def __repr__(self) -> str:
        """Detailed representation of port manager"""
        return (
            f"PortManager(start_port={self.start_port}, "
            f"end_port={self.end_port}, "
            f"assignments={self.get_assignments()})"
        )
