"""
Cloudformation deploy class which also streams events and changeset information
"""

# Copyright 2012-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import logging
import math
import sys
import time
from collections import OrderedDict, deque
from datetime import datetime
from typing import Dict, List, Optional

import botocore

from samcli.commands._utils.table_print import MIN_OFFSET, newline_per_item, pprint_column_names, pprint_columns
from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.commands.deploy.exceptions import (
    ChangeSetError,
    DeployBucketInDifferentRegionError,
    DeployFailedError,
    DeployStackOutPutFailedError,
    DeployStackStatusMissingError,
)
from samcli.lib.deploy.utils import DeployColor, FailureMode
from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name, mktempfile
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.colors import Colored, Colors
from samcli.lib.utils.s3 import parse_s3_url
from samcli.lib.utils.time import to_datetime, utc_to_timestamp

LOG = logging.getLogger(__name__)

DESCRIBE_STACK_EVENTS_FORMAT_STRING = (
    "{ResourceStatus:<{0}} {ResourceType:<{1}} {LogicalResourceId:<{2}} {ResourceStatusReason:<{3}}"
)
DESCRIBE_STACK_EVENTS_DEFAULT_ARGS = OrderedDict(
    {
        "ResourceStatus": "ResourceStatus",
        "ResourceType": "ResourceType",
        "LogicalResourceId": "LogicalResourceId",
        "ResourceStatusReason": "ResourceStatusReason",
    }
)

DESCRIBE_STACK_EVENTS_TABLE_HEADER_NAME = "CloudFormation events from stack operations (refresh every {} seconds)"

DESCRIBE_CHANGESET_FORMAT_STRING = "{Operation:<{0}} {LogicalResourceId:<{1}} {ResourceType:<{2}} {Replacement:<{3}}"
DESCRIBE_CHANGESET_DEFAULT_ARGS = OrderedDict(
    {
        "Operation": "Operation",
        "LogicalResourceId": "LogicalResourceId",
        "ResourceType": "ResourceType",
        "Replacement": "Replacement",
    }
)

DESCRIBE_CHANGESET_TABLE_HEADER_NAME = "CloudFormation stack changeset"

OUTPUTS_FORMAT_STRING = "{Outputs:<{0}}"
OUTPUTS_DEFAULTS_ARGS = OrderedDict({"Outputs": "Outputs"})

OUTPUTS_TABLE_HEADER_NAME = "CloudFormation outputs from deployed stack"

# 500ms of sleep time between stack checks and describe stack events.
DEFAULT_CLIENT_SLEEP = 0.5


class Deployer:
    def __init__(self, cloudformation_client, changeset_prefix="samcli-deploy", client_sleep=DEFAULT_CLIENT_SLEEP):
        self._client = cloudformation_client
        self.changeset_prefix = changeset_prefix
        try:
            self.client_sleep = float(client_sleep)
        except ValueError:
            self.client_sleep = DEFAULT_CLIENT_SLEEP
        if self.client_sleep <= 0:
            self.client_sleep = DEFAULT_CLIENT_SLEEP
        # 2000ms of backoff time which is exponentially used, when there are exceptions during describe stack events
        self.backoff = 2
        # Maximum number of attempts before raising exception back up the chain.
        self.max_attempts = 3
        self.deploy_color = DeployColor()
        self._colored = Colored()

    # pylint: disable=inconsistent-return-statements
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

            LOG.debug("Unknown ClientError recieved: %s. Cannot determine if stack exists.", str(e))
            raise DeployFailedError(stack_name=stack_name, msg=str(e)) from e
        except botocore.exceptions.BotoCoreError as e:
            # If there are credentials, environment errors,
            # catch that and throw a deploy failed error.

            LOG.debug("Botocore Exception : %s", str(e))
            raise DeployFailedError(stack_name=stack_name, msg=str(e)) from e

        except Exception as e:
            # We don't know anything about this exception. Don't handle
            LOG.debug("Unable to get stack details.", exc_info=e)
            raise e

    def create_changeset(
        self, stack_name, cfn_template, parameter_values, capabilities, role_arn, notification_arns, s3_uploader, tags
    ):
        """
        Call Cloudformation to create a changeset and wait for it to complete

        :param stack_name: Name or ID of stack
        :param cfn_template: CloudFormation template string
        :param parameter_values: Template parameters object
        :param capabilities: Array of capabilities passed to CloudFormation
        :param role_arn: the Arn of the role to create changeset
        :param notification_arns: Arns for sending notifications
        :param s3_uploader: S3Uploader object to upload files to S3 buckets
        :param tags: Array of tags passed to CloudFormation
        :return:
        """
        if not self.has_stack(stack_name):
            changeset_type = "CREATE"
            # When creating a new stack, UsePreviousValue=True is invalid.
            # For such parameters, users should either override with new value,
            # or set a Default value in template to successfully create a stack.
            parameter_values = [x for x in parameter_values if not x.get("UsePreviousValue", False)]
        else:
            changeset_type = "UPDATE"
            # UsePreviousValue not valid if parameter is new
            summary = self._client.get_template_summary(StackName=stack_name)
            existing_parameters = [parameter["ParameterKey"] for parameter in summary["Parameters"]]
            parameter_values = [
                x
                for x in parameter_values
                if not (x.get("UsePreviousValue", False) and x["ParameterKey"] not in existing_parameters)
            ]

        # Each changeset will get a unique name based on time.
        # Description is also setup based on current date and that SAM CLI is used.
        kwargs = {
            "ChangeSetName": self.changeset_prefix + str(int(time.time())),
            "StackName": stack_name,
            "TemplateBody": cfn_template,
            "ChangeSetType": changeset_type,
            "Parameters": parameter_values,
            "Description": "Created by SAM CLI at {0} UTC".format(datetime.utcnow().isoformat()),
            "Tags": tags,
        }

        kwargs = self._process_kwargs(kwargs, s3_uploader, capabilities, role_arn, notification_arns)
        return self._create_change_set(stack_name=stack_name, changeset_type=changeset_type, **kwargs)

    @staticmethod
    def _process_kwargs(
        kwargs: dict,
        s3_uploader: Optional[S3Uploader],
        capabilities: Optional[List[str]],
        role_arn: Optional[str],
        notification_arns: Optional[List[str]],
    ) -> dict:
        # If an S3 uploader is available, use TemplateURL to deploy rather than
        # TemplateBody. This is required for large templates.
        if s3_uploader:
            with mktempfile() as temporary_file:
                temporary_file.write(kwargs.pop("TemplateBody"))
                temporary_file.flush()
                remote_path = get_uploaded_s3_object_name(file_path=temporary_file.name, extension="template")
                # TemplateUrl property requires S3 URL to be in path-style format
                parts = parse_s3_url(s3_uploader.upload(temporary_file.name, remote_path), version_property="Version")
                kwargs["TemplateURL"] = s3_uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))

        # don't set these arguments if not specified to use existing values
        if capabilities is not None:
            kwargs["Capabilities"] = capabilities
        if role_arn is not None:
            kwargs["RoleARN"] = role_arn
        if notification_arns is not None:
            kwargs["NotificationARNs"] = notification_arns
        return kwargs

    def _create_change_set(self, stack_name, changeset_type, **kwargs):
        try:
            resp = self._client.create_change_set(**kwargs)
            return resp, changeset_type
        except botocore.exceptions.ClientError as ex:
            if "The bucket you are attempting to access must be addressed using the specified endpoint" in str(ex):
                raise DeployBucketInDifferentRegionError(f"Failed to create/update stack {stack_name}") from ex
            raise ChangeSetError(stack_name=stack_name, msg=str(ex)) from ex

        except Exception as ex:
            LOG.debug("Unable to create changeset", exc_info=ex)
            raise ChangeSetError(stack_name=stack_name, msg=str(ex)) from ex

    @pprint_column_names(
        format_string=DESCRIBE_CHANGESET_FORMAT_STRING,
        format_kwargs=DESCRIBE_CHANGESET_DEFAULT_ARGS,
        table_header=DESCRIBE_CHANGESET_TABLE_HEADER_NAME,
    )
    def describe_changeset(self, change_set_id, stack_name, **kwargs):
        """
        Call Cloudformation to describe a changeset

        :param change_set_id: ID of the changeset
        :param stack_name: Name of the CloudFormation stack
        :param kwargs: Other arguments to pass to pprint_columns()
        :return: dictionary of changes described in the changeset.
        """
        paginator = self._client.get_paginator("describe_change_set")
        response_iterator = paginator.paginate(ChangeSetName=change_set_id, StackName=stack_name)
        changes = {"Add": [], "Modify": [], "Remove": []}
        changes_showcase = {"Add": "+ Add", "Modify": "* Modify", "Remove": "- Delete"}
        changeset = False
        for item in response_iterator:
            cf_changes = item.get("Changes")
            for change in cf_changes:
                changeset = True
                resource_props = change.get("ResourceChange")
                action = resource_props.get("Action")
                changes[action].append(
                    {
                        "LogicalResourceId": resource_props.get("LogicalResourceId"),
                        "ResourceType": resource_props.get("ResourceType"),
                        "Replacement": (
                            "N/A" if resource_props.get("Replacement") is None else resource_props.get("Replacement")
                        ),
                    }
                )

        for k, v in changes.items():
            for value in v:
                row_color = self.deploy_color.get_changeset_action_color(action=k)
                pprint_columns(
                    columns=[
                        changes_showcase.get(k, k),
                        value["LogicalResourceId"],
                        value["ResourceType"],
                        value["Replacement"],
                    ],
                    width=kwargs["width"],
                    margin=kwargs["margin"],
                    format_string=DESCRIBE_CHANGESET_FORMAT_STRING,
                    format_args=kwargs["format_args"],
                    columns_dict=DESCRIBE_CHANGESET_DEFAULT_ARGS.copy(),
                    color=row_color,
                )

        if not changeset:
            # There can be cases where there are no changes,
            # but could be an an addition of a SNS notification topic.
            pprint_columns(
                columns=["-", "-", "-", "-"],
                width=kwargs["width"],
                margin=kwargs["margin"],
                format_string=DESCRIBE_CHANGESET_FORMAT_STRING,
                format_args=kwargs["format_args"],
                columns_dict=DESCRIBE_CHANGESET_DEFAULT_ARGS.copy(),
            )

        return changes

    def wait_for_changeset(self, changeset_id, stack_name):
        """
        Waits until the changeset creation completes

        :param changeset_id: ID or name of the changeset
        :param stack_name:   Stack name
        """
        sys.stdout.write("\n\nWaiting for changeset to be created..\n\n")
        sys.stdout.flush()

        # Wait for changeset to be created
        waiter = self._client.get_waiter("change_set_create_complete")
        # Use default client_sleep to set the delay between polling
        # To override use SAM_CLI_POLL_DELAY environment variable
        waiter_config = {"Delay": self.client_sleep}
        try:
            waiter.wait(ChangeSetName=changeset_id, StackName=stack_name, WaiterConfig=waiter_config)
        except botocore.exceptions.WaiterError as ex:
            resp = ex.last_response
            status = resp.get("Status")
            reason = resp.get("StatusReason")

            if not status or not reason:
                # not a CFN DescribeChangeSet response, re-raising
                LOG.debug("Failed while waiting for changeset: %s", ex)
                raise ex

            if (
                status == "FAILED"
                and "The submitted information didn't contain changes." in reason
                or "No updates are to be performed" in reason
            ):
                raise deploy_exceptions.ChangeEmptyError(stack_name=stack_name)

            raise ChangeSetError(stack_name=stack_name, msg=f"ex: {ex} Status: {status}. Reason: {reason}") from ex

    def execute_changeset(self, changeset_id, stack_name, disable_rollback):
        """
        Calls CloudFormation to execute changeset

        :param changeset_id: ID of the changeset
        :param stack_name: Name or ID of the stack
        :param disable_rollback: Preserve the state of previously provisioned resources when an operation fails.
        """
        try:
            self._client.execute_change_set(
                ChangeSetName=changeset_id, StackName=stack_name, DisableRollback=disable_rollback
            )
        except botocore.exceptions.ClientError as ex:
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

    def get_last_event_time(self, stack_name, default_time=time.time()):
        """
        Finds the last event time stamp that presents for the stack, if not return the default_time
        :param stack_name: Name or ID of the stack
        :param default_time: the default unix epoch time to be returned in case if the stack provided does not exist
        :return: unix epoch
        """
        try:
            return utc_to_timestamp(
                self._client.describe_stack_events(StackName=stack_name)["StackEvents"][0]["Timestamp"]
            )
        except KeyError:
            return default_time

    @pprint_column_names(
        format_string=DESCRIBE_STACK_EVENTS_FORMAT_STRING,
        format_kwargs=DESCRIBE_STACK_EVENTS_DEFAULT_ARGS,
        table_header=DESCRIBE_STACK_EVENTS_TABLE_HEADER_NAME,
        display_sleep=True,
    )
    def describe_stack_events(
        self, stack_name: str, time_stamp_marker: float, on_failure: FailureMode = FailureMode.ROLLBACK, **kwargs
    ):
        """
        Calls CloudFormation to get current stack events
        :param stack_name: Name or ID of the stack
        :param time_stamp_marker: last event time on the stack to start streaming events from.
        :param on_failure: The action to take if the stack fails to deploy
        :param kwargs: Other arguments to pass to pprint_columns()
        """

        stack_change_in_progress = True
        events = set()
        retry_attempts = 0

        while stack_change_in_progress and retry_attempts <= self.max_attempts:
            try:
                # Only sleep if there have been no retry_attempts
                LOG.debug("Trial # %d to get the stack %s create events", retry_attempts, stack_name)
                time.sleep(0 if retry_attempts else self.client_sleep)
                paginator = self._client.get_paginator("describe_stack_events")
                response_iterator = paginator.paginate(StackName=stack_name)

                # Event buffer
                new_events = deque()  # type: deque

                for event_items in response_iterator:
                    for event in event_items["StackEvents"]:
                        LOG.debug("Stack Event: %s", event)
                        # Skip already shown old event entries or former deployments
                        if utc_to_timestamp(event["Timestamp"]) <= time_stamp_marker:
                            LOG.debug(
                                "Skip previous event as time_stamp_marker: %s is after the event time stamp: %s",
                                to_datetime(time_stamp_marker),
                                event["Timestamp"],
                            )
                            break
                        if event["EventId"] not in events:
                            events.add(event["EventId"])
                            # Events are in reverse chronological order
                            # Pushing in front reverse the order to display older events first
                            new_events.appendleft(event)
                    else:  # go to next loop (page of events) if not break from inside loop
                        LOG.debug("Still in describe_stack_events loop, got to next page")
                        continue
                    break  # reached here only if break from inner loop!
                LOG.debug("Exit from the describe event loop")
                # Override timestamp marker with latest event (last in deque)
                if len(new_events) > 0:
                    time_stamp_marker = utc_to_timestamp(new_events[-1]["Timestamp"])

                for new_event in new_events:
                    row_color = self.deploy_color.get_stack_events_status_color(status=new_event["ResourceStatus"])
                    pprint_columns(
                        # Print the detailed status beside the status if it is present
                        # E.g. CREATE_IN_PROGRESS - CONFIGURATION_COMPLETE
                        columns=[
                            (
                                (new_event["ResourceStatus"] + " - " + new_event["DetailedStatus"])
                                if "DetailedStatus" in new_event
                                else new_event["ResourceStatus"]
                            ),
                            new_event["ResourceType"],
                            new_event["LogicalResourceId"],
                            new_event.get("ResourceStatusReason", "-"),
                        ],
                        width=kwargs["width"],
                        margin=kwargs["margin"],
                        format_string=DESCRIBE_STACK_EVENTS_FORMAT_STRING,
                        format_args=kwargs["format_args"],
                        columns_dict=DESCRIBE_STACK_EVENTS_DEFAULT_ARGS.copy(),
                        color=row_color,
                    )
                    # Skip events from another consecutive deployment triggered during sleep by another process
                    if self._is_root_stack_event(new_event) and self._check_stack_not_in_progress(
                        new_event["ResourceStatus"]
                    ):
                        LOG.debug(
                            "Stack %s is not in progress. Its status is %s, and event is %s",
                            stack_name,
                            new_event["ResourceStatus"],
                            new_event,
                        )
                        stack_change_in_progress = False
                        break

                # Reset retry attempts if iteration is a success to use client_sleep again
                retry_attempts = 0
            except botocore.exceptions.ClientError as ex:
                if (
                    "Stack with id {0} does not exist".format(stack_name) in str(ex)
                    and on_failure == FailureMode.DELETE
                ):
                    LOG.debug("Stack %s does not exist", stack_name)
                    return

                LOG.debug("Trial # %d failed due to exception %s", retry_attempts, str(ex))

                retry_attempts = retry_attempts + 1
                if retry_attempts > self.max_attempts:
                    LOG.error("Describing stack events for %s failed: %s", stack_name, str(ex))
                    return
                # Sleep in exponential backoff mode
                time.sleep(math.pow(self.backoff, retry_attempts))

    @staticmethod
    def _is_root_stack_event(event: Dict) -> bool:
        return bool(
            event["ResourceType"] == "AWS::CloudFormation::Stack"
            and event["StackName"] == event["LogicalResourceId"]
            and event["PhysicalResourceId"] == event["StackId"]
        )

    @staticmethod
    def _check_stack_not_in_progress(status: str) -> bool:
        return "IN_PROGRESS" not in status

    def wait_for_execute(
        self,
        stack_name: str,
        stack_operation: str,
        disable_rollback: bool,
        on_failure: FailureMode = FailureMode.ROLLBACK,
        time_stamp_marker: float = 0,
        max_wait_duration: int = 60,
    ) -> None:
        """
        Wait for stack operation to execute and return when execution completes.
        If the stack has "Outputs," they will be printed.

        Parameters
        ----------
        stack_name : str
            The name of the stack
        stack_operation : str
            The type of the stack operation, 'CREATE' or 'UPDATE'
        disable_rollback : bool
            Preserves the state of previously provisioned resources when an operation fails
        on_failure : FailureMode
            The action to take when the operation fails
        time_stamp_marker:
            last event time on the stack to start streaming events from.
        max_wait_duration:
            The maximum duration in minutes to wait for the deployment to complete.
        """
        sys.stdout.write(
            "\n{} - Waiting for stack create/update "
            "to complete\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        sys.stdout.flush()

        self.describe_stack_events(stack_name, time_stamp_marker, on_failure)

        # Pick the right waiter
        if stack_operation == "CREATE":
            waiter = self._client.get_waiter("stack_create_complete")
        elif stack_operation == "UPDATE":
            waiter = self._client.get_waiter("stack_update_complete")
        else:
            raise RuntimeError("Invalid stack operation type {0}".format(stack_operation))

        delay = 30
        max_attempts = max_wait_duration * 60 // delay

        # Poll every 30 seconds. Polling too frequently risks hitting rate limits
        # on CloudFormation's DescribeStacks API
        waiter_config = {"Delay": delay, "MaxAttempts": max_attempts}

        try:
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
        except botocore.exceptions.WaiterError as ex:
            LOG.debug("Execute stack waiter exception", exc_info=ex)
            if disable_rollback and on_failure is not FailureMode.DELETE:
                # This will only display the message if disable rollback is set or if DO_NOTHING is specified
                msg = self._gen_deploy_failed_with_rollback_disabled_msg(stack_name)
                LOG.info(self._colored.color_log(msg=msg, color=Colors.FAILURE), extra=dict(markup=True))

            raise deploy_exceptions.DeployFailedError(stack_name=stack_name, msg=str(ex))

        try:
            outputs = self.get_stack_outputs(stack_name=stack_name, echo=False)
            if outputs:
                self._display_stack_outputs(outputs)
        except DeployStackOutPutFailedError as ex:
            # Show exception if we aren't deleting stacks
            if on_failure != FailureMode.DELETE:
                raise ex

    def create_and_wait_for_changeset(
        self, stack_name, cfn_template, parameter_values, capabilities, role_arn, notification_arns, s3_uploader, tags
    ):
        try:
            result, changeset_type = self.create_changeset(
                stack_name, cfn_template, parameter_values, capabilities, role_arn, notification_arns, s3_uploader, tags
            )
            self.wait_for_changeset(result["Id"], stack_name)
            self.describe_changeset(result["Id"], stack_name)
            return result, changeset_type
        except botocore.exceptions.ClientError as ex:
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

    def create_stack(self, **kwargs):
        stack_name = kwargs.get("StackName")
        try:
            resp = self._client.create_stack(**kwargs)
            return resp
        except botocore.exceptions.ClientError as ex:
            if "The bucket you are attempting to access must be addressed using the specified endpoint" in str(ex):
                raise DeployBucketInDifferentRegionError(f"Failed to create/update stack {stack_name}") from ex
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

        except Exception as ex:
            LOG.debug("Unable to create stack", exc_info=ex)
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

    def update_stack(self, **kwargs):
        stack_name = kwargs.get("StackName")
        try:
            resp = self._client.update_stack(**kwargs)
            return resp
        except botocore.exceptions.ClientError as ex:
            if "The bucket you are attempting to access must be addressed using the specified endpoint" in str(ex):
                raise DeployBucketInDifferentRegionError(f"Failed to create/update stack {stack_name}") from ex
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

        except Exception as ex:
            LOG.debug("Unable to update stack", exc_info=ex)
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

    def sync(
        self,
        stack_name: str,
        cfn_template: str,
        parameter_values: List[Dict],
        capabilities: Optional[List[str]],
        role_arn: Optional[str],
        notification_arns: Optional[List[str]],
        s3_uploader: Optional[S3Uploader],
        tags: Optional[Dict],
        on_failure: FailureMode,
    ):
        """
        Call the sync command to directly update stack or create stack

        Parameters
        ----------
        :param stack_name: The name of the stack
        :param cfn_template: CloudFormation template string
        :param parameter_values: Template parameters object
        :param capabilities: Array of capabilities passed to CloudFormation
        :param role_arn: the Arn of the role to create changeset
        :param notification_arns: Arns for sending notifications
        :param s3_uploader: S3Uploader object to upload files to S3 buckets
        :param tags: Array of tags passed to CloudFormation
        :param on_failure: FailureMode enum indicating the action to take on stack creation failure
        :return:
        """
        exists = self.has_stack(stack_name)

        if not exists:
            # When creating a new stack, UsePreviousValue=True is invalid.
            # For such parameters, users should either override with new value,
            # or set a Default value in template to successfully create a stack.
            parameter_values = [x for x in parameter_values if not x.get("UsePreviousValue", False)]
        else:
            summary = self._client.get_template_summary(StackName=stack_name)
            existing_parameters = [parameter["ParameterKey"] for parameter in summary["Parameters"]]
            parameter_values = [
                x
                for x in parameter_values
                if not (x.get("UsePreviousValue", False) and x["ParameterKey"] not in existing_parameters)
            ]

        kwargs = {
            "StackName": stack_name,
            "TemplateBody": cfn_template,
            "Parameters": parameter_values,
            "Tags": tags,
        }

        kwargs = self._process_kwargs(kwargs, s3_uploader, capabilities, role_arn, notification_arns)

        try:
            disable_rollback = False
            if on_failure == FailureMode.DO_NOTHING:
                disable_rollback = True
            msg = ""

            if exists:
                kwargs["DisableRollback"] = disable_rollback  # type: ignore
                # get the latest stack event, and use 0 in case if the stack does not exist
                marker_time = self.get_last_event_time(stack_name, 0)
                result = self.update_stack(**kwargs)
                self.wait_for_execute(
                    stack_name, "UPDATE", disable_rollback, on_failure=on_failure, time_stamp_marker=marker_time
                )
                msg = "\nStack update succeeded. Sync infra completed.\n"
            else:
                # Pass string representation of enum
                kwargs["OnFailure"] = str(on_failure)

                result = self.create_stack(**kwargs)
                self.wait_for_execute(stack_name, "CREATE", disable_rollback, on_failure=on_failure)
                msg = "\nStack creation succeeded. Sync infra completed.\n"

            LOG.info(self._colored.color_log(msg=msg, color=Colors.SUCCESS), extra=dict(markup=True))

            return result
        except botocore.exceptions.ClientError as ex:
            raise DeployFailedError(stack_name=stack_name, msg=str(ex)) from ex

    @staticmethod
    @pprint_column_names(
        format_string=OUTPUTS_FORMAT_STRING, format_kwargs=OUTPUTS_DEFAULTS_ARGS, table_header=OUTPUTS_TABLE_HEADER_NAME
    )
    def _display_stack_outputs(stack_outputs: List[Dict], **kwargs) -> None:
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
                    color=Colors.SUCCESS,
                    replace_whitespace=False,
                    break_long_words=False,
                    drop_whitespace=False,
                )
            newline_per_item(stack_outputs, counter)

    def get_stack_outputs(self, stack_name, echo=True):
        try:
            stacks_description = self._client.describe_stacks(StackName=stack_name)
            try:
                outputs = stacks_description["Stacks"][0]["Outputs"]
                if echo:
                    sys.stdout.write("\nStack {stack_name} outputs:\n".format(stack_name=stack_name))
                    sys.stdout.flush()
                    self._display_stack_outputs(stack_outputs=outputs)
                return outputs
            except KeyError:
                return None

        except botocore.exceptions.ClientError as ex:
            raise DeployStackOutPutFailedError(stack_name=stack_name, msg=str(ex)) from ex

    def rollback_delete_stack(self, stack_name: str):
        """
        Try to rollback the stack to a sucessful state, if there is no good state then delete the stack

        Parameters
        ----------
        :param stack_name: str
            The name of the stack
        """
        kwargs = {
            "StackName": stack_name,
        }
        current_state = self._get_stack_status(stack_name)

        try:
            if current_state == "UPDATE_FAILED":
                LOG.info("Stack %s failed to update, rolling back stack to previous state...", stack_name)

                # get the latest stack event
                marker_time = self.get_last_event_time(stack_name, 0)
                self._client.rollback_stack(**kwargs)
                self.describe_stack_events(stack_name, marker_time, FailureMode.DELETE)
                self._rollback_wait(stack_name)

                current_state = self._get_stack_status(stack_name)

            failed_states = ["CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED"]

            if current_state in failed_states:
                LOG.info("Stack %s failed to create/update correctly, deleting stack", stack_name)

                # get the latest stack event
                marker_time = self.get_last_event_time(stack_name, 0)
                self._client.delete_stack(**kwargs)

                # only a stack that failed to create will have stack events, deleting
                # from a ROLLBACK_COMPLETE state will not return anything
                # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/cloudformation.html#CloudFormation.Client.delete_stack
                if current_state == "CREATE_FAILED":
                    self.describe_stack_events(stack_name, marker_time, FailureMode.DELETE)

                waiter = self._client.get_waiter("stack_delete_complete")
                waiter.wait(StackName=stack_name, WaiterConfig={"Delay": 30, "MaxAttempts": 120})

                LOG.info("\nStack %s has been deleted", stack_name)
            else:
                LOG.info("Stack %s has rolled back successfully", stack_name)
        except botocore.exceptions.ClientError as ex:
            raise DeployStackStatusMissingError(stack_name) from ex
        except botocore.exceptions.WaiterError:
            LOG.error(
                "\nStack %s failed to delete properly! Please manually clean up any persistent resources.",
                stack_name,
            )
        except KeyError:
            LOG.info("Stack %s is not found, skipping", stack_name)

    def _get_stack_status(self, stack_name: str) -> str:
        """
        Returns the status of the stack

        Parameters
        ----------
        :param stack_name: str
            The name of the stack

        Parameters
        ----------
        :return: str
            A string representing the status of the stack
        """
        stack = self._client.describe_stacks(StackName=stack_name)
        stack_status = str(stack["Stacks"][0]["StackStatus"])

        return stack_status

    def _rollback_wait(self, stack_name: str, wait_time: int = 30, max_retries: int = 120):
        """
        Manual waiter for rollback status, waits until we get *_ROLLBACK_COMPLETE or ROLLBACK_FAILED

        Parameters
        ----------
        :param stack_name: str
            The name of the stack
        :param wait_time: int
            The time to wait between polls, default 30 seconds
        :param max_retries: int
            The number of polls before timing out
        """
        status = ""
        retries = 0

        while retries < max_retries:
            status = self._get_stack_status(stack_name)

            if "ROLLBACK_COMPLETE" in status or status == "ROLLBACK_FAILED":
                return

            retries = retries + 1
            time.sleep(wait_time)

        LOG.error(
            "Stack %s never reached a *_ROLLBACK_COMPLETE or ROLLBACK_FAILED state, we got %s instead.",
            stack_name,
            status,
        )

    @staticmethod
    def _gen_deploy_failed_with_rollback_disabled_msg(stack_name):
        return """\nFailed to deploy. Automatic rollback disabled for this deployment.\n
Actions you can take next
=========================
[*] Fix issues and try deploying again
[*] Roll back stack to the last known stable state: aws cloudformation rollback-stack --stack-name {stack_name}
""".format(
            stack_name=stack_name
        )
