# ABOUTME: Unit tests for TenantIdType CLI parameter validation
# ABOUTME: Tests tenant-id format validation and error handling

import pytest
from click import BadParameter

from samcli.cli.types import TenantIdType


class TestTenantIdType:
    def setup_method(self):
        self.tenant_id_type = TenantIdType()

    def test_valid_tenant_ids(self):
        """Test valid tenant-id formats pass validation"""
        valid_ids = [
            "customer-123",
            "tenant_456",
            "org.domain.com",
            "user@company.com",
            "path/to/resource",
            "key=value+data",
            "simple123",
            "a",  # minimum length
            "a" * 256,  # maximum length
            "mixed-chars_123.test@domain.com/path=value+extra data",
        ]

        for tenant_id in valid_ids:
            result = self.tenant_id_type.convert(tenant_id, None, None)
            assert result == tenant_id

    def test_invalid_tenant_ids_raise_bad_parameter(self):
        """Test invalid tenant-id formats raise BadParameter with correct message"""
        from unittest.mock import Mock

        mock_param = Mock()
        mock_param.opts = ["--tenant-id"]

        # Test length validation
        with pytest.raises(BadParameter) as exc_info:
            self.tenant_id_type.convert("", mock_param, None)
        assert "must be between 1 and 256 characters" in str(exc_info.value)

        with pytest.raises(BadParameter) as exc_info:
            self.tenant_id_type.convert("a" * 257, mock_param, None)
        assert "must be between 1 and 256 characters" in str(exc_info.value)

        # Test spaces-only validation
        with pytest.raises(BadParameter) as exc_info:
            self.tenant_id_type.convert("   ", mock_param, None)
        assert "cannot be empty or contain only whitespace" in str(exc_info.value)

        # Test format validation
        invalid_chars = ["tenant#123", "tenant|123", "tenant<123", "tenant>123"]
        for tenant_id in invalid_chars:
            with pytest.raises(BadParameter) as exc_info:
                self.tenant_id_type.convert(tenant_id, mock_param, None)
            assert "contains invalid characters" in str(exc_info.value)
            assert "Allowed characters are" in str(exc_info.value)

    def test_none_value_returns_none(self):
        """Test None value passes through unchanged"""
        result = self.tenant_id_type.convert(None, None, None)
        assert result is None

    def test_type_name(self):
        """Test the parameter type name is correct"""
        assert self.tenant_id_type.name == "string"
