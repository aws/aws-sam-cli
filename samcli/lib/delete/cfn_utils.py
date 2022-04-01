"""
Delete Cloudformation stacks and s3 files
"""

import logging


from typing import Dict, List, Optional
from botocore.exceptions import ClientError, BotoCoreError, WaiterError
from samcli.commands.delete.exceptions import DeleteFailedError, FetchTemplateFailedError, CfDeleteFailedStatusError


LOG = logging.getLogger(__name__)


class CfnUtils:
    def __init__(self, cloudformation_client):
        self._client = cloudformation_client

    def has_stack(self, stack_name: str) -> bool:
        """
        Checks if a CloudFormation stack with given name exists

        :param stack_name: Name or ID of the stack
        :return: True if stack exists. False otherwise
        """
        try:
            resp = self._client.describe_stacks(StackName=stack_name)
            if not resp["Stacks"]:
                return False

            stack = resp["Stacks"][0]
            if stack["EnableTerminationProtection"]:
                message = "Stack cannot be deleted while TerminationProtection is enabled."
                raise DeleteFailedError(stack_name=stack_name, msg=message)

            # Note: Stacks with REVIEW_IN_PROGRESS can be deleted
            # using delete_stack but get_template does not return
            # the template_str for this stack restricting deletion of
            # artifacts.
            return bool(stack["StackStatus"] != "REVIEW_IN_PROGRESS")

        except ClientError as e:
            # If a stack does not exist, describe_stacks will throw an
            # exception. Unfortunately we don't have a better way than parsing
            # the exception msg to understand the nature of this exception.

            if "Stack with id {0} does not exist".format(stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", stack_name)
                return False
            LOG.error("ClientError Exception : %s", str(e))
            raise DeleteFailedError(stack_name=stack_name, msg=str(e)) from e
        except BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Botocore Exception : %s", str(e))
            raise DeleteFailedError(stack_name=stack_name, msg=str(e)) from e

    def get_stack_template(self, stack_name: str, stage: str) -> Dict:
        """
        Return the Cloudformation template of the given stack_name

        :param stack_name: Name or ID of the stack
        :param stage: The Stage of the template Original or Processed
        :return: Template body of the stack
        """
        try:
            resp = self._client.get_template(StackName=stack_name, TemplateStage=stage)
            if not resp["TemplateBody"]:
                return {}
            return dict(resp)

        except (ClientError, BotoCoreError) as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Failed to fetch template for the stack : %s", str(e))
            raise FetchTemplateFailedError(stack_name=stack_name, msg=str(e)) from e

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.error("Unable to get stack details.", exc_info=e)
            raise e

    def delete_stack(self, stack_name: str, retain_resources: Optional[List] = None):
        """
        Delete the Cloudformation stack with the given stack_name

        :param stack_name: Name or ID of the stack
        :param retain_resources: List of repositories to retain if the stack has DELETE_FAILED status.
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

    def wait_for_delete(self, stack_name):
        """
        Waits until the delete stack completes

        :param stack_name:   Stack name
        """

        # Wait for Delete to Finish
        waiter = self._client.get_waiter("stack_delete_complete")
        # Poll every 5 seconds.
        waiter_config = {"Delay": 30}
        try:
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
        except WaiterError as ex:

            if "DELETE_FAILED" in str(ex):
                raise CfDeleteFailedStatusError(stack_name=stack_name, msg="ex: {0}".format(ex)) from ex

            raise DeleteFailedError(stack_name=stack_name, msg="ex: {0}".format(ex)) from ex
