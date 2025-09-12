"""
Unit tests for PortManager
"""

import socket
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from samcli.commands.local.lib.port_manager import PortManager, PortExhaustedException


class TestPortManager(TestCase):
    def setUp(self):
        self.port_manager = PortManager(start_port=3001, end_port=3005)

    def test_init_with_valid_range(self):
        """Test initialization with valid port range"""
        pm = PortManager(3000, 3010)
        self.assertEqual(pm.start_port, 3000)
        self.assertEqual(pm.end_port, 3010)
        self.assertEqual(pm.assigned_ports, {})
        self.assertEqual(pm.reserved_ports, set())

    def test_init_with_invalid_range(self):
        """Test initialization with invalid port range"""
        with self.assertRaises(ValueError):
            PortManager(3010, 3000)  # Start > End
        
        with self.assertRaises(ValueError):
            PortManager(3000, 70000)  # End > 65535

    def test_init_with_privileged_port_warning(self):
        """Test warning for privileged ports"""
        with patch('samcli.commands.local.lib.port_manager.LOG') as mock_log:
            PortManager(80, 443)
            mock_log.warning.assert_called()

    @patch('socket.socket')
    def test_allocate_port_success(self, mock_socket_class):
        """Test successful port allocation"""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        port = self.port_manager.allocate_port("TestFunction")
        
        self.assertEqual(port, 3001)
        self.assertEqual(self.port_manager.assigned_ports["TestFunction"], 3001)
        self.assertIn(3001, self.port_manager.reserved_ports)

    def test_allocate_port_already_assigned(self):
        """Test allocating port for already assigned function"""
        self.port_manager.assigned_ports["TestFunction"] = 3002
        
        port = self.port_manager.allocate_port("TestFunction")
        
        self.assertEqual(port, 3002)

    @patch('socket.socket')
    def test_allocate_preferred_port_success(self, mock_socket_class):
        """Test allocating a specific preferred port"""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        port = self.port_manager.allocate_port("TestFunction", preferred_port=3003)
        
        self.assertEqual(port, 3003)
        self.assertEqual(self.port_manager.assigned_ports["TestFunction"], 3003)

    def test_allocate_preferred_port_out_of_range(self):
        """Test allocating preferred port outside configured range"""
        with self.assertRaises(ValueError):
            self.port_manager.allocate_port("TestFunction", preferred_port=4000)

    @patch('socket.socket')
    def test_allocate_port_exhausted(self, mock_socket_class):
        """Test port exhaustion scenario"""
        # Mock socket to always fail (port unavailable)
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        with self.assertRaises(PortExhaustedException):
            self.port_manager.allocate_port("TestFunction")

    @patch('socket.socket')
    def test_is_port_available_true(self, mock_socket_class):
        """Test checking if port is available"""
        mock_socket = MagicMock()
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        result = self.port_manager._is_port_available(3001)
        
        self.assertTrue(result)
        mock_socket.bind.assert_called_with(('', 3001))

    @patch('socket.socket')
    def test_is_port_available_false(self, mock_socket_class):
        """Test checking if port is unavailable"""
        mock_socket = MagicMock()
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value.__enter__.return_value = mock_socket
        
        result = self.port_manager._is_port_available(3001)
        
        self.assertFalse(result)

    def test_is_port_available_already_reserved(self):
        """Test checking port that's already reserved"""
        self.port_manager.reserved_ports.add(3001)
        
        result = self.port_manager._is_port_available(3001)
        
        self.assertFalse(result)

    def test_release_port(self):
        """Test releasing an assigned port"""
        self.port_manager.assigned_ports["TestFunction"] = 3001
        self.port_manager.reserved_ports.add(3001)
        
        released_port = self.port_manager.release_port("TestFunction")
        
        self.assertEqual(released_port, 3001)
        self.assertNotIn("TestFunction", self.port_manager.assigned_ports)
        self.assertNotIn(3001, self.port_manager.reserved_ports)

    def test_release_port_not_assigned(self):
        """Test releasing port for function with no assignment"""
        released_port = self.port_manager.release_port("NonExistentFunction")
        
        self.assertIsNone(released_port)

    def test_release_all(self):
        """Test releasing all ports"""
        self.port_manager.assigned_ports = {
            "Function1": 3001,
            "Function2": 3002,
            "Function3": 3003
        }
        self.port_manager.reserved_ports = {3001, 3002, 3003}
        
        self.port_manager.release_all()
        
        self.assertEqual(self.port_manager.assigned_ports, {})
        self.assertEqual(self.port_manager.reserved_ports, set())

    def test_get_assignments(self):
        """Test getting current port assignments"""
        self.port_manager.assigned_ports = {
            "Function1": 3001,
            "Function2": 3002
        }
        
        assignments = self.port_manager.get_assignments()
        
        self.assertEqual(assignments, {"Function1": 3001, "Function2": 3002})
        # Ensure it's a copy, not the original
        assignments["Function3"] = 3003
        self.assertNotIn("Function3", self.port_manager.assigned_ports)

    def test_get_port_for_function(self):
        """Test getting port for specific function"""
        self.port_manager.assigned_ports["TestFunction"] = 3001
        
        port = self.port_manager.get_port_for_function("TestFunction")
        
        self.assertEqual(port, 3001)

    def test_get_port_for_function_not_assigned(self):
        """Test getting port for unassigned function"""
        port = self.port_manager.get_port_for_function("NonExistentFunction")
        
        self.assertIsNone(port)

    def test_is_port_in_range(self):
        """Test checking if port is in configured range"""
        self.assertTrue(self.port_manager.is_port_in_range(3001))
        self.assertTrue(self.port_manager.is_port_in_range(3003))
        self.assertTrue(self.port_manager.is_port_in_range(3005))
        self.assertFalse(self.port_manager.is_port_in_range(3000))
        self.assertFalse(self.port_manager.is_port_in_range(3006))

    def test_get_available_count(self):
        """Test getting count of available ports"""
        self.assertEqual(self.port_manager.get_available_count(), 5)
        
        self.port_manager.assigned_ports = {
            "Function1": 3001,
            "Function2": 3002
        }
        
        self.assertEqual(self.port_manager.get_available_count(), 3)

    def test_str_representation(self):
        """Test string representation"""
        self.port_manager.assigned_ports = {"Function1": 3001}
        
        result = str(self.port_manager)
        
        self.assertIn("3001-3005", result)
        self.assertIn("assigned=1", result)
        self.assertIn("available=4", result)

    def test_repr_representation(self):
        """Test detailed representation"""
        self.port_manager.assigned_ports = {"Function1": 3001}
        
        result = repr(self.port_manager)
        
        self.assertIn("start_port=3001", result)
        self.assertIn("end_port=3005", result)
        self.assertIn("Function1", result)
