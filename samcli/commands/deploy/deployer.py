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

import collections
import logging
import sys
import time
from datetime import datetime

import botocore
import click
import pytz

from samcli.commands.deploy import exceptions as deploy_exceptions
from samcli.commands.package.artifact_exporter import mktempfile, parse_s3_url
from samcli.lib.utils.colors import Colored

LOG = logging.getLogger(__name__)

ChangeSetResult = collections.namedtuple("ChangeSetResult", ["changeset_id", "changeset_type"])


class Deployer(object):
    def __init__(self, cloudformation_client, changeset_prefix="samcli-cloudformation-package-deploy-"):
        self._client = cloudformation_client
        self.changeset_prefix = changeset_prefix
        self.color = Colored()

    def has_stack(self, stack_name):
        """
        Checks if a CloudFormation stack with given name exists

        :param stack_name: Name or ID of the stack
        :return: True if stack exists. False otherwise
        """
        try:
            resp = self._client.describe_stacks(StackName=stack_name)
            if len(resp["Stacks"]) != 1:
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
            msg = str(e)

            if "Stack with id {0} does not exist".format(stack_name) in msg:
                LOG.debug("Stack with id {0} does not exist".format(stack_name))
                return False
            else:
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
        :param tags: Array of tags passed to CloudFormation
        :return:
        """

        now = datetime.utcnow().isoformat()
        description = "Created by SAM CLI at {0} UTC".format(now)

        # Each changeset will get a unique name based on time
        changeset_name = self.changeset_prefix + str(int(time.time()))

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

        kwargs = {
            "ChangeSetName": changeset_name,
            "StackName": stack_name,
            "TemplateBody": cfn_template,
            "ChangeSetType": changeset_type,
            "Parameters": parameter_values,
            "Capabilities": capabilities,
            "Description": description,
            "Tags": tags,
        }

        # If an S3 uploader is available, use TemplateURL to deploy rather than
        # TemplateBody. This is required for large templates.
        if s3_uploader:
            with mktempfile() as temporary_file:
                temporary_file.write(kwargs.pop("TemplateBody"))
                temporary_file.flush()
                url = s3_uploader.upload_with_dedup(temporary_file.name, "template")
                # TemplateUrl property requires S3 URL to be in path-style format
                parts = parse_s3_url(url, version_property="Version")
                kwargs["TemplateURL"] = s3_uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))

        # don't set these arguments if not specified to use existing values
        if role_arn is not None:
            kwargs["RoleARN"] = role_arn
        if notification_arns is not None:
            kwargs["NotificationARNs"] = notification_arns
        try:
            resp = self._client.create_change_set(**kwargs)
            return resp, changeset_type
        except Exception as ex:
            LOG.debug("Unable to create changeset", exc_info=ex)
            raise ex

    def describe_changeset(self, change_set_id, stack_name):
        """
        Call Cloudformation to describe a changeset

        :param change_set_id: ID of the changeset
        :param stack_name: Name of the CloudFormation stack
        :return: dictionary of changes described in the changeset.
        """
        paginator = self._client.get_paginator("describe_change_set")
        response_iterator = paginator.paginate(ChangeSetName=change_set_id, StackName=stack_name)
        changes = {"Add": [], "Modify": [], "Remove": []}
        for item in response_iterator:
            cf_changes = item.get("Changes")
            for change in cf_changes:
                resource_props = change.get("ResourceChange")
                action = resource_props.get("Action")
                logical_id = resource_props.get("LogicalResourceId")
                resource_type = resource_props.get("ResourceType")
                changes[action].append({"LogicalResourceId": logical_id, "ResourceType": resource_type})
        return changes

    def wait_for_changeset(self, changeset_id, stack_name):
        """
        Waits until the changeset creation completes

        :param changeset_id: ID or name of the changeset
        :param stack_name:   Stack name
        :return: Latest status of the create-change-set operation
        """
        sys.stdout.write("\nWaiting for changeset to be created..\n")
        sys.stdout.flush()

        # Wait for changeset to be created
        waiter = self._client.get_waiter("change_set_create_complete")
        # Poll every 5 seconds. Changeset creation should be fast
        waiter_config = {"Delay": 5}
        try:
            waiter.wait(ChangeSetName=changeset_id, StackName=stack_name, WaiterConfig=waiter_config)
        except botocore.exceptions.WaiterError as ex:
            LOG.debug("Create changeset waiter exception", exc_info=ex)

            resp = ex.last_response
            status = resp["Status"]
            reason = resp["StatusReason"]

            if (
                status == "FAILED"
                and "The submitted information didn't contain changes." in reason
                or "No updates are to be performed" in reason
            ):
                raise deploy_exceptions.ChangeEmptyError(stack_name=stack_name)

            raise RuntimeError(
                "Failed to create the changeset: {0} " "Status: {1}. Reason: {2}".format(ex, status, reason)
            )

    def execute_changeset(self, changeset_id, stack_name):
        """
        Calls CloudFormation to execute changeset

        :param changeset_id: ID of the changeset
        :param stack_name: Name or ID of the stack
        :return: Response from execute-change-set call
        """
        return self._client.execute_change_set(ChangeSetName=changeset_id, StackName=stack_name)

    def get_last_event_time(self, stack_name):
        try:
            return self._client.describe_stack_events(StackName=stack_name)["StackEvents"][0]["Timestamp"]
        except KeyError:
            return pytz.utc.localize(datetime.utcnow())

    def desribe_stack_events(self, stack_name, utc_now):
        """
        Calls CloudFormation to get current stack events
        :param stack_name: Name or ID of the stack
        :return:
        """

        stack_change_in_progress = True
        events = set()

        time.sleep(1)

        width, _ = click.get_terminal_size()
        width = width - (width % 3)
        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))
        click.secho(
            "{LogicalResourceId:<{lr_w}} {ResourceType:<{rt_w}} {ResourceStatus:<{rs_w}}".format(
                LogicalResourceId="LogicalResourceId",
                ResourceType="ResourceType",
                ResourceStatus="ResourceStatus",
                lr_w=int(width / 3),
                rt_w=int(width / 3),
                rs_w=int(width / 3) - 1,
            )
        )
        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))
        while stack_change_in_progress:
            describe_stacks_resp = self._client.describe_stacks(StackName=stack_name)
            if (
                "COMPLETE" in describe_stacks_resp["Stacks"][0]["StackStatus"]
                and "CLEANUP" not in describe_stacks_resp["Stacks"][0]["StackStatus"]
            ):
                stack_change_in_progress = False
            describe_stack_events_resp = self._client.describe_stack_events(StackName=stack_name)
            time.sleep(0.1)
            for event in describe_stack_events_resp["StackEvents"]:
                if event["EventId"] not in events and event["Timestamp"] > utc_now:
                    events.add(event["EventId"])
                    click.secho(
                        "{LogicalResourceId:<{lr_w}} {ResourceType:<{rt_w}} {ResourceStatus:<{rs_w}}".format(
                            LogicalResourceId=event["LogicalResourceId"],
                            ResourceType=event["ResourceType"],
                            ResourceStatus=event["ResourceStatus"],
                            lr_w=int(width / 3),
                            rt_w=int(width / 3),
                            rs_w=(int(width / 3) - 1),
                        ),
                        fg="yellow",
                    )

        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))

    def wait_for_execute(self, stack_name, changeset_type):

        sys.stdout.write("Waiting for stack create/update to complete\n")
        sys.stdout.flush()

        self.desribe_stack_events(stack_name, self.get_last_event_time(stack_name))

        # Pick the right waiter
        if changeset_type == "CREATE":
            waiter = self._client.get_waiter("stack_create_complete")
        elif changeset_type == "UPDATE":
            waiter = self._client.get_waiter("stack_update_complete")
        else:
            raise RuntimeError("Invalid changeset type {0}".format(changeset_type))

        # Poll every 5 seconds. Optimizing for the case when the stack has only
        # minimal changes, such the Code for Lambda Function
        waiter_config = {"Delay": 5, "MaxAttempts": 720}

        try:
            waiter.wait(StackName=stack_name, WaiterConfig=waiter_config)
        except botocore.exceptions.WaiterError as ex:
            LOG.debug("Execute changeset waiter exception", exc_info=ex)

            raise deploy_exceptions.DeployFailedError(stack_name=stack_name)

    def create_and_wait_for_changeset(
        self, stack_name, cfn_template, parameter_values, capabilities, role_arn, notification_arns, s3_uploader, tags
    ):

        result, changeset_type = self.create_changeset(
            stack_name, cfn_template, parameter_values, capabilities, role_arn, notification_arns, s3_uploader, tags
        )
        self.wait_for_changeset(result["Id"], stack_name)
        changes = self.describe_changeset(result["Id"], stack_name)
        width, _ = click.get_terminal_size()
        width = width - (width % 3)
        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))
        click.secho(
            "{Operation:<{lr_w}} {LogicalResourceId:<{rt_w}} {ResourceType:<{rs_w}}".format(
                Operation="Operation",
                LogicalResourceId="LogicalResourceId",
                ResourceType="ResourceType",
                lr_w=int(width / 3),
                rt_w=int(width / 3),
                rs_w=int(width / 3) - 1,
            )
        )
        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))
        color = {"Add": "green", "Modify": "yellow", "Remove": "red"}
        for k, v in changes.items():
            for value in v:
                click.secho(
                    "{Operation:<{lr_w}} {LogicalResourceId:<{rt_w}} {ResourceType:<{rs_w}}".format(
                        Operation=k,
                        LogicalResourceId=value["LogicalResourceId"],
                        ResourceType=value["ResourceType"],
                        lr_w=int(width / 3),
                        rt_w=int(width / 3),
                        rs_w=int(width / 3) - 1,
                    ),
                    fg=color[k],
                )

        click.secho("-" * (int(width / 3) + int(width / 3) + (int(width / 3) - 1)))
        return result, changeset_type
