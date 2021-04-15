"""
Cloudformation stack output display
"""

import logging
from collections import OrderedDict
import sys
from typing import Dict, List

import botocore

from samcli.commands.show.exceptions import ShowStackOutputFailedError
from samcli.commands._utils.table_print import pprint_column_names, pprint_columns, newline_per_item, MIN_OFFSET

LOG = logging.getLogger(__name__)

OUTPUTS_FORMAT_STRING = "{Outputs:<{0}}"
OUTPUTS_DEFAULTS_ARGS = OrderedDict({"Outputs": "Outputs"})

OUTPUTS_TABLE_HEADER_NAME = "CloudFormation outputs from deployed stack"


class StackOutput:
    def __init__(self, cloudformation_client):
        self._client = cloudformation_client

    def has_stack(self, stack_name):
        """
        Checks if a CloudFormation stack with given name exists

        :param stack_name: Name or ID of the stack
        :return: True if stack exists. False otherwise
        """
        try:
            resp = self._client.describe_stacks(StackName=stack_name)
            if not resp["Stacks"]:
                return False

            # When you run CreateChangeSet on a a stack that does not exist,
            # CloudFormation will create a stack and set it's status
            # REVIEW_IN_PROGRESS. However this stack is cannot be manipulated
            # by "update" commands. Under this circumstances, we treat like
            # this stack does not exist and call CreateChangeSet will
            # ChangeSetType set to CREATE and not UPDATE.
            stack = resp["Stacks"][0]
            return stack["StackStatus"] != "REVIEW_IN_PROGRESS"

        except botocore.exceptions.ClientError as e:
            # If a stack does not exist, describe_stacks will throw an
            # exception. Unfortunately we don't have a better way than parsing
            # the exception msg to understand the nature of this exception.

            if "Stack with id {0} does not exist".format(stack_name) in str(e):
                LOG.debug("Stack with id %s does not exist", stack_name)
                return False

        except botocore.exceptions.BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a deploy failed error.

            LOG.debug("Botocore Exception : %s", str(e))
            raise ShowStackOutputFailedError(stack_name=stack_name, msg=str(e)) from e

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.debug("Unable to get stack details.", exc_info=e)
            raise e

    def get_stack_outputs(self, stack_name, echo=True):
        try:
            stacks_description = self._client.describe_stacks(StackName=stack_name)
            try:
                outputs = stacks_description["Stacks"][0]["Outputs"]
                if echo:
                    sys.stdout.write("\nStack {stack_name} outputs:\n".format(stack_name=stack_name))
                    sys.stdout.flush()
                    self.display_stack_outputs(stack_outputs=outputs)
                return outputs
            except KeyError:
                return None

        except botocore.exceptions.ClientError as ex:
            raise ShowStackOutputFailedError(stack_name=stack_name, msg=str(ex)) from ex

    @staticmethod
    @pprint_column_names(
        format_string=OUTPUTS_FORMAT_STRING, format_kwargs=OUTPUTS_DEFAULTS_ARGS, table_header=OUTPUTS_TABLE_HEADER_NAME
    )
    def display_stack_outputs(stack_outputs: List[Dict], **kwargs) -> None:
        for counter, output in enumerate(stack_outputs):
            for k, v in [
                ("Key", output.get("OutputKey")),
                ("Description", output.get("Description", "-")),
                ("Value", output.get("OutputValue")),
            ]:
                pprint_columns(
                    columns=["{k:<{0}}{v:<{0}}".format(MIN_OFFSET, k=k, v=v)],
                    width=kwargs["width"],
                    margin=kwargs["margin"],
                    format_string=OUTPUTS_FORMAT_STRING,
                    format_args=kwargs["format_args"],
                    columns_dict=OUTPUTS_DEFAULTS_ARGS.copy(),
                    color="green",
                    replace_whitespace=False,
                    break_long_words=False,
                    drop_whitespace=False,
                )
            newline_per_item(stack_outputs, counter)
