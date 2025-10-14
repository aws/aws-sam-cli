"""
Unit tests for nested stack changeset support in deployer.py
Tests for Issue #2406 - Support for nested stack changeset
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError, WaiterError

from samcli.lib.deploy.deployer import Deployer
from samcli.commands.deploy.exceptions import ChangeSetError, ChangeEmptyError


class TestNestedStackChangesetSupport:
    """Test nested stack changeset functionality"""

    def setup_method(self):
        self.cf_client = Mock()
        self.deployer = Deployer(cloudformation_client=self.cf_client)

    def test_include_nested_stacks_in_changeset_creation(self):
        """Test that IncludeNestedStacks is set to True in changeset creation"""
        stack_name = "test-stack"
        cfn_template = "template content"
        parameter_values = []
        capabilities = ["CAPABILITY_IAM"]
        role_arn = "arn:aws:iam::123456789:role/test"
        notification_arns = []
        s3_uploader = None
        tags = []

        # Mock has_stack to return False (new stack)
        with patch.object(self.deployer, "has_stack", return_value=False):
            with patch.object(self.deployer, "_create_change_set") as mock_create:
                mock_create.return_value = ({"Id": "changeset-123"}, "CREATE")

                self.deployer.create_changeset(
                    stack_name,
                    cfn_template,
                    parameter_values,
                    capabilities,
                    role_arn,
                    notification_arns,
                    s3_uploader,
                    tags,
                )

                # Verify _create_change_set was called
                assert mock_create.called

                # Get the kwargs passed to _create_change_set
                call_kwargs = mock_create.call_args[1]

                # Verify IncludeNestedStacks is True
                assert (
                    call_kwargs.get("IncludeNestedStacks") == True
                ), "IncludeNestedStacks should be set to True in changeset creation"

    def test_describe_changeset_with_nested_stacks(self):
        """Test that describe_changeset handles nested stack changes"""
        change_set_id = "changeset-123"
        stack_name = "parent-stack"

        # Mock paginator response with nested stack
        mock_paginator = Mock()
        self.cf_client.get_paginator.return_value = mock_paginator

        # Parent stack changes with a nested stack
        mock_paginator.paginate.return_value = [
            {
                "Changes": [
                    {
                        "ResourceChange": {
                            "Action": "Add",
                            "LogicalResourceId": "NestedStack",
                            "ResourceType": "AWS::CloudFormation::Stack",
                            "Replacement": None,
                            "ChangeSetId": "arn:aws:cloudformation:us-east-1:123:changeSet/nested-cs/abc-123",
                        }
                    }
                ]
            }
        ]

        # Mock nested changeset response
        self.cf_client.describe_change_set.return_value = {
            "Changes": [
                {
                    "ResourceChange": {
                        "Action": "Add",
                        "LogicalResourceId": "DynamoTable",
                        "ResourceType": "AWS::DynamoDB::Table",
                        "Replacement": None,
                    }
                }
            ]
        }

        # Call describe_changeset (decorator handles display)
        result = self.deployer.describe_changeset(change_set_id, stack_name)

        # Verify nested changeset was fetched
        self.cf_client.describe_change_set.assert_called_once()

        # Verify result contains parent stack changes
        assert result is not False
        assert "Add" in result
        assert len(result["Add"]) == 1
        assert result["Add"][0]["LogicalResourceId"] == "NestedStack"

    def test_get_nested_changeset_error_extracts_arn(self):
        """Test that _get_nested_changeset_error can extract nested changeset ARN"""
        status_reason = (
            "Nested change set arn:aws:cloudformation:us-east-1:123456789:changeSet/"
            "nested-stack-name/abc-123-def-456 was not successfully created: Currently in FAILED."
        )

        # Mock describe_change_set to return error details
        self.cf_client.describe_change_set.return_value = {
            "Status": "FAILED",
            "StatusReason": "Property 'InvalidProperty' is not valid for AWS::DynamoDB::Table",
        }

        result = self.deployer._get_nested_changeset_error(status_reason)

        # Verify error message was extracted
        assert result is not None
        assert "nested-stack-name" in result
        assert "InvalidProperty" in result

    def test_get_nested_changeset_error_handles_parse_failure(self):
        """Test that _get_nested_changeset_error handles invalid status reason gracefully"""
        status_reason = "Some other error message without nested changeset ARN"

        result = self.deployer._get_nested_changeset_error(status_reason)

        # Should return None if can't parse
        assert result is None

        # Should not have called describe_change_set
        self.cf_client.describe_change_set.assert_not_called()

    def test_wait_for_changeset_with_nested_error(self):
        """Test that wait_for_changeset fetches nested changeset errors"""
        changeset_id = "changeset-123"
        stack_name = "test-stack"

        # Mock waiter to raise error with nested changeset message
        mock_waiter = Mock()
        self.cf_client.get_waiter.return_value = mock_waiter

        nested_error_reason = (
            "Nested change set arn:aws:cloudformation:us-east-1:123456789:changeSet/"
            "nested-stack/abc-123 was not successfully created: Currently in FAILED."
        )

        waiter_error = WaiterError(
            name="ChangeSetCreateComplete",
            reason="Waiter encountered terminal failure",
            last_response={"Status": "FAILED", "StatusReason": nested_error_reason},
        )
        mock_waiter.wait.side_effect = waiter_error

        # Mock nested changeset describe
        self.cf_client.describe_change_set.return_value = {
            "Status": "FAILED",
            "StatusReason": "Property 'InvalidProperty' is not valid for AWS::DynamoDB::Table",
        }

        with patch("sys.stdout"):
            with pytest.raises(ChangeSetError) as exc_info:
                self.deployer.wait_for_changeset(changeset_id, stack_name)

        # Verify the error message includes nested stack details
        error_msg = str(exc_info.value)
        assert "nested-stack" in error_msg or "InvalidProperty" in error_msg

    def test_empty_changeset_still_raises_correctly(self):
        """Test that empty changeset error is still raised correctly"""
        changeset_id = "changeset-123"
        stack_name = "test-stack"

        # Mock waiter to raise empty changeset error
        mock_waiter = Mock()
        self.cf_client.get_waiter.return_value = mock_waiter

        waiter_error = WaiterError(
            name="ChangeSetCreateComplete",
            reason="Waiter encountered terminal failure",
            last_response={"Status": "FAILED", "StatusReason": "The submitted information didn't contain changes."},
        )
        mock_waiter.wait.side_effect = waiter_error

        with patch("sys.stdout"):
            with pytest.raises(ChangeEmptyError):
                self.deployer.wait_for_changeset(changeset_id, stack_name)


class TestBackwardCompatibility:
    """Test that changes don't break existing functionality"""

    def setup_method(self):
        self.cf_client = Mock()
        self.deployer = Deployer(cloudformation_client=self.cf_client)

    def test_no_changes_scenario(self):
        """Test that no changes scenario works correctly"""
        change_set_id = "changeset-123"
        stack_name = "test-stack"

        mock_paginator = Mock()
        self.cf_client.get_paginator.return_value = mock_paginator

        # Empty changes
        mock_paginator.paginate.return_value = [{"Changes": []}]

        result = self.deployer.describe_changeset(change_set_id, stack_name)

        # When no changes, _display_changeset_changes returns False
        # which describe_changeset then handles by displaying "-" placeholders
        # The actual return is False from _display_changeset_changes when changeset_found is False
        assert result == False or result == {"Add": [], "Modify": [], "Remove": []}
