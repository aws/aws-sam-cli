"""
Unit tests for DurableContext
"""

import unittest
from unittest.mock import Mock, patch

from samcli.commands.local.cli_common.durable_context import DurableContext


class TestDurableContext(unittest.TestCase):
    """Test cases for DurableContext class"""

    @patch("samcli.commands.local.cli_common.durable_context.DurableFunctionsEmulatorContainer")
    def test_context_manager_success(self, mock_emulator_class):
        """Test successful context manager usage"""
        # Arrange
        mock_emulator = Mock()
        mock_emulator.port = 9014
        mock_emulator.start_or_attach.return_value = False  # New container created
        mock_emulator.lambda_client = Mock()
        mock_emulator_class.return_value = mock_emulator

        # Act
        with DurableContext() as context:
            # Assert
            mock_emulator_class.assert_called_once()
            mock_emulator.start_or_attach.assert_called_once()
            self.assertEqual(context.client, mock_emulator.lambda_client)

        # Assert cleanup
        mock_emulator.stop.assert_called_once()

    def test_client_property_without_context(self):
        """Test accessing client property outside context raises error"""
        # Arrange
        context = DurableContext()

        # Act & Assert
        with self.assertRaises(RuntimeError) as cm:
            _ = context.client

        self.assertIn("DurableContext not initialized", str(cm.exception))

    @patch("samcli.commands.local.cli_common.durable_context.DurableFunctionsEmulatorContainer")
    def test_cleanup_on_exception(self, mock_emulator_class):
        """Test that cleanup happens even when exception occurs"""
        # Arrange
        mock_emulator = Mock()
        mock_emulator.port = 9014
        mock_emulator.start_or_attach.return_value = False  # New container created
        mock_emulator.lambda_client = Mock()
        mock_emulator_class.return_value = mock_emulator

        # Act & Assert
        try:
            with DurableContext():
                raise Exception("Test exception")
        except Exception:
            pass

        # Assert cleanup still happened
        mock_emulator.stop.assert_called_once()

    @patch("samcli.commands.local.cli_common.durable_context.DurableFunctionsEmulatorContainer")
    def test_reuses_existing_running_container(self, mock_emulator_class):
        """Test that existing running container is reused"""
        # Arrange - mock existing running container
        mock_emulator = Mock()
        mock_emulator.port = 9014
        mock_emulator.start_or_attach.return_value = True  # Container was reused
        mock_emulator.lambda_client = Mock()
        mock_emulator_class.return_value = mock_emulator

        # Act
        with DurableContext() as context:
            # Should call start_or_attach which handles container and client reuse
            mock_emulator.start_or_attach.assert_called_once()
            self.assertEqual(context.client, mock_emulator.lambda_client)

        # Should not call stop on emulator (since we reused existing)
        mock_emulator.stop.assert_not_called()
