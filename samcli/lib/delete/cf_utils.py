"""
Delete Cloudformation stacks and s3 files
"""

import logging

from typing import Dict
from botocore.exceptions import ClientError, BotoCoreError
from samcli.commands.delete.exceptions import DeleteFailedError, FetchTemplateFailedError

LOG = logging.getLogger(__name__)


class CfUtils:
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

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.error("Unable to get stack details.", exc_info=e)
            raise e

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

    def delete_stack(self, stack_name: str):
        """
        Delete the Cloudformation stack with the given stack_name

        :param stack_name: Name or ID of the stack
        """
        try:
            self._client.delete_stack(StackName=stack_name)

        except (ClientError, BotoCoreError) as e:
            # If there are credentials, environment errors,
            # catch that and throw a delete failed error.

            LOG.error("Failed to delete stack : %s", str(e))
            raise DeleteFailedError(stack_name=stack_name, msg=str(e)) from e

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.error("Failed to delete stack. ", exc_info=e)
            raise e
