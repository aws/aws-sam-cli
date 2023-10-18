"""
Delete Cloudformation stacks and s3 files
"""

import json
import logging
from typing import List, Optional

from botocore.exceptions import BotoCoreError, ClientError, WaiterError

from samcli.commands.delete.exceptions import (
    CfDeleteFailedStatusError,
    DeleteFailedError,
    FetchChangeSetError,
    FetchTemplateFailedError,
    NoChangeSetFoundError,
    StackFetchError,
    StackProtectionEnabledError,
)

LOG = logging.getLogger(__name__)


class CfnUtils:
    def __init__(self, cloudformation_client):
        self._client = cloudformation_client

    def can_delete_stack(self, stack_name: str) -> bool:
        """
        Checks if a CloudFormation stack with given name exists

        Parameters
        ----------
        stack_name: str
            Name or ID of the stack

        Returns
        -------
        bool
            True if stack exists. False otherwise

        Raises
        ------
        StackFetchError
            Raised when the boto call fails to get stack information
        StackProtectionEnabledError
            Raised when the stack is protected from deletions
        """
        try:
            resp = self._client.describe_stacks(StackName=stack_name)
            if not resp["Stacks"]:
                return False

            stack = resp["Stacks"][0]
            if stack["EnableTerminationProtection"]:
                raise StackProtectionEnabledError(stack_name=stack_name)

            return True

        except ClientError as e:
            # If a stack does not exist, describe_stacks will throw an
            # exception. Unfortunately we don't have a better way than parsing
            # the exception msg to understand the nature of this exception.

            if "Stack with id {0} does not exist".format(stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", stack_name)
                return False
            LOG.error("ClientError Exception : %s", str(e))
            raise StackFetchError(stack_name=stack_name, msg=str(e)) from e
        except BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Botocore Exception : %s", str(e))
            raise StackFetchError(stack_name=stack_name, msg=str(e)) from e

    def get_stack_template(self, stack_name: str, stage: str) -> str:
        """
        Return the Cloudformation template of the given stack_name

        Parameters
        ----------

        stack_name: str
            Name or ID of the stack
        stage: str
            The Stage of the template Original or Processed

        Returns
        -------
        str
            Template body of the stack

        Raises
        ------
        FetchTemplateFailedError
            Raised when boto calls or parsing fails to fetch template
        """
        try:
            resp = self._client.get_template(StackName=stack_name, TemplateStage=stage)
            template = resp.get("TemplateBody", "")

            # stack may not have template, check the change set
            if not template:
                change_set_name = self._get_change_set_name(stack_name)

                if change_set_name:
                    # the stack has a change set, use the template from this
                    resp = self._client.get_template(
                        StackName=stack_name, TemplateStage=stage, ChangeSetName=change_set_name
                    )
                    template = resp.get("TemplateBody", "")

            # template variable can be of type string or of type dict which does not return
            # nicely as a string, so it is dumped instead
            if isinstance(template, dict):
                return json.dumps(template)

            return str(template)

        except (ClientError, BotoCoreError) as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Failed to fetch template for the stack : %s", str(e))
            raise FetchTemplateFailedError(stack_name=stack_name, msg=str(e)) from e
        except FetchChangeSetError as ex:
            raise FetchTemplateFailedError(stack_name=stack_name, msg=str(ex)) from ex
        except NoChangeSetFoundError as ex:
            msg = "Failed to find a change set to fetch the template"
            raise FetchTemplateFailedError(stack_name=stack_name, msg=msg) from ex
        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.error("Unable to get stack details.", exc_info=e)
            raise e

    def delete_stack(self, stack_name: str, retain_resources: Optional[List] = None):
        """
        Delete the Cloudformation stack with the given stack_name

        Parameters
        ----------
        stack_name:
            str Name or ID of the stack
        retain_resources: Optional[List]
            List of repositories to retain if the stack has DELETE_FAILED status.

        Raises
        ------
        DeleteFailedError
            Raised when the boto delete_stack call fails
        """
        if not retain_resources:
            retain_resources = []
        try:
            self._client.delete_stack(StackName=stack_name, RetainResources=retain_resources)

        except (ClientError, BotoCoreError) as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Failed to delete stack : %s", str(e))
            raise DeleteFailedError(stack_name=stack_name, msg=str(e)) from e

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.error("Failed to delete stack. ", exc_info=e)
            raise e

    def wait_for_delete(self, stack_name: str):
        """
        Waits until the delete stack completes

        Parameter
        ---------
        stack_name: str
            The name of the stack to watch when deleting

        Raises
        ------
        CfDeleteFailedStatusError
            Raised when the stack fails to delete
        DeleteFailedError
            Raised when the stack fails to wait when polling for status
        """

        # Wait for Delete to Finish
        waiter = self._client.get_waiter("stack_delete_complete")
        # Remove `MaxAttempts` from waiter_config.
        # Regression: https://github.com/aws/aws-sam-cli/issues/4361
        waiter_config = {"Delay": 30}
        try:
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
        except WaiterError as ex:
            stack_status = ex.last_response.get("Stacks", [{}])[0].get("StackStatusReason", "")  # type: ignore

            if "DELETE_FAILED" in str(ex):
                raise CfDeleteFailedStatusError(
                    stack_name=stack_name, stack_status=stack_status, msg="ex: {0}".format(ex)
                ) from ex

            raise DeleteFailedError(stack_name=stack_name, stack_status=stack_status, msg="ex: {0}".format(ex)) from ex

    def _get_change_set_name(self, stack_name: str) -> str:
        """
        Returns the name of the change set for a stack

        Parameters
        ----------
        stack_name: str
            The name of the stack to find a change set

        Returns
        -------
        str
            The name of a change set

        Raises
        ------
        FetchChangeSetError
            Raised if there are boto call errors or parsing errors
        NoChangeSetFoundError
            Raised if a stack does not have any change sets
        """
        try:
            change_sets: dict = self._client.list_change_sets(StackName=stack_name)
        except (ClientError, BotoCoreError) as ex:
            LOG.debug("Failed to perform boto call to fetch change sets")
            raise FetchChangeSetError(stack_name=stack_name, msg=str(ex)) from ex

        change_sets = change_sets.get("Summaries", [])

        if len(change_sets) > 1:
            LOG.info(
                "More than one change set was found, please clean up any "
                "lingering template files that may exist in the S3 bucket."
            )

        if len(change_sets) > 0:
            change_set = change_sets[0]
            change_set_name = str(change_set.get("ChangeSetName", ""))

            LOG.debug(f"Returning change set: {change_set}")
            return change_set_name

        LOG.debug("Stack contains no change sets")
        raise NoChangeSetFoundError(stack_name=stack_name)
