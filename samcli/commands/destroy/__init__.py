# -*- coding: utf-8 -*-
"""
Init command to scaffold a project app from a template
"""
import logging
import sys

import boto3
import click
from botocore.exceptions import ClientError, WaiterError

from samcli.cli.main import pass_context, common_options
from samcli.lib.telemetry.metrics import track_command

LOG = logging.getLogger(__name__)

SHORT_HELP = "Destroys a deployed CloudFormation stack."

HELP_TEXT = """The sam destroy command destroys a Cloudformation Stack.

\b
e.g. sam destroy -stack-name sam-app
"""


@click.command(
    "destroy",
    short_help=SHORT_HELP,
    context_settings={
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
    help=HELP_TEXT,
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "--stack-name",
    required=True,
    help="The name of the AWS CloudFormation stack you're deploying to. "
    "If you specify an existing stack, the command updates the stack. "
    "If you specify a new stack, the command creates it.",
)
@click.option(
    "--retain-resources",
    required=False,
    multiple=True,
    default=[],
    help="For  stacks  in  the DELETE_FAILED state, a list of resource logical"
    "IDs that are associated with the resources you want to retain.  During  deletion,  "
    "AWS  CloudFormation  deletes  the stack but does not "
    "delete the retained resources."
    "Retaining resources is useful when you  cannot  delete  a  resource,"
    "such as a non-empty S3 bucket, but you want to delete the stack.",
)
@click.option(
    "--role-arn",
    required=False,
    help="""The Amazon Resource Name (ARN) of an AWS Identity and Access Management (IAM) role that AWS
              CloudFormation assumes to delete the stack. AWS CloudFormation uses the role's credentials to make
              calls on your behalf. If you don't specify a value, AWS CloudFormation uses the role  that was
              previously  associated with the stack. If no role is available, AWS CloudFormation uses a temporary
              session that is  generated  from your user credentials.""",
)
@click.option(
    "--client-request-token",
    required=False,
    help="""A unique identifier for this DeleteStack request. Specify this token
                  if you plan to retry requests so that AWS CloudFormation knows  that
                  you're  not  attempting  to  delete  a stack with the same name. You
                  might retry DeleteStack requests to ensure that  AWS  CloudFormation
                  successfully received them.

                  Learn more at aws cloudformation destroy help
                  """,
)
@click.option(
    "-w",
    "--wait",
    required=False,
    is_flag=True,
    help="Option to wait for Stack deletion",
)
@click.option(
    "--wait-time",
    required=False,
    type=click.INT,
    help="The time to wait for stack to delete in seconds. Used with --wait. The default is 5 minutes",
    default=300,
)
@click.option(
    "-f",
    "--force",
    "force",
    required=False,
    is_flag=True,
    help="Deletes the Stack without cli prompt",
)
@common_options
@pass_context
@track_command
def cli(
    ctx,
    args,
    stack_name,
    retain_resources,
    role_arn,
    client_request_token,
    wait,
    wait_time,
    force=False,
):
    """
    Destroys the stack
    """
    # All logic must be implemented in the `do_cli` method. This helps ease unit tests
    do_cli(
        ctx,
        stack_name,
        retain_resources,
        role_arn,
        client_request_token,
        wait,
        wait_time,
        force,
    )  # pragma: no cover


def verify_stack_exists(client, stack_name, required_status=None):
    """
    Checks that the stack exists

    If any of the resources are in a state of  DELETE_FAILED, they need to be in the retain_resources section.

    The stack must also exist in order to be deleted
    Parameters
    -----------
    client: boto3 client
        The cloudformation boto3 client used for making calls
    stack_name: str
        The stack name of the stack to check
    required_status: str
        A status that should be checked for by the stack

    """
    try:
        described_stack = client.describe_stacks(StackName=stack_name)
    except ClientError:
        click.secho(
            "The stack {} must exist in order to be deleted".format(stack_name),
            fg="red",
        )
        sys.exit(1)

    if (
        required_status and described_stack["Stacks"][0]["StackStatus"] != required_status
    ):
        click.secho(
            "The stack {} does not have the correct status {}".format(
                stack_name, required_status
            ),
            fg="red",
        )
        sys.exit(1)


def check_nested_stack(client, stack_name):
    """
    Prompts if there is a nested stack in the CloudResource.
    This is to prevent people from deleting more than they expected.
    Parameters
    -----------
    client: boto3 client
        The cloudformation boto3 client used for making calls
    stack_name: str
        The stack name of the stack to check
    """
    template = client.get_template(StackName=stack_name, TemplateStage="Processed")
    nested_stacks = [
        logical_id
        for logical_id, value in template.get("Resources", {}).items()
        if value.get("Type") == "AWS::CloudFormation::Stack"
    ]

    click.confirm(
        "The stack {} is a nested stack with the following resources: {}. Are you want to destroy them?".format(
            stack_name, nested_stacks
        ),
        default=True,
        abort=True,
    )


def verify_stack_retain_resources(client, stack_name, retain_resources=None):
    """
    Checks that if any of the resources are in a state of DELETE_FAILED, they need to be in the retain_resources section

    The stack must also exist in order to be deleted
    Parameters
    -----------
    client: boto3 client
        The cloudformation boto3 client used for making calls
    stack_name: str
        The stack name of the stack to check
    retain_resources: list
        A list of resources that should be reatined. This is used when checking if all DELETE_FAILED are in the
        retain_resources
    """
    if not retain_resources:
        retain_resources = []
    paginator = client.get_paginator("describe_stack_events")
    response_iterator = paginator.paginate(StackName=stack_name)
    for iterator in response_iterator:
        events = [
            event
            for event in iterator.get("StackEvents")
            if event.get("ResourceStatus") == "DELETE_FAILED"
        ]
        for event in events:
            logical_id = event.get("LogicalResourceId")
            if logical_id not in retain_resources:
                click.secho(
                    "The logicalId {} of the resource in the stack {} must be included in retain_resource since the "
                    "deletion failed".format(logical_id, stack_name),
                    fg="red",
                )
                sys.exit(1)


def do_cli(  # pylint: disable=too-many-statements
    ctx,
    stack_name,
    retain_resources=None,
    role_arn=None,
    client_request_token=None,
    wait=None,
    wait_time=None,
    force=False,
):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    if not force:
        click.confirm(
            "Are you sure you want to delete the stack {}?".format(stack_name),
            default=True,
            abort=True,
        )
    cfn = boto3.client("cloudformation", region_name="us-west-1")

    verify_stack_exists(cfn, stack_name)
    verify_stack_retain_resources(cfn, stack_name, retain_resources)
    if not force:
        check_nested_stack(cfn, stack_name)

    args = {
        "RoleARN": role_arn,
        "ClientRequestToken": client_request_token,
        "RetainResources": retain_resources,
    }

    # Filters the args dictionary so that no argument with type `None` is passed in. This is because deleting a stack
    # with boto3 only accepts non `None` arguments.
    args = {k: v for k, v in args.items() if v is not None}

    try:
        cfn.delete_stack(StackName=stack_name, **args)
    except ClientError as e:
        if "TerminationProtection" in e.response["Error"]["Message"]:
            msg = (
                "The stack {stack_name} has TerminationProtection turned on. Disable it on the aws console at " +
                "https://us-west-1.console.aws.amazon.com/cloudformation/home \n or " +
                "run aws cloudformation update-termination-protection --stack-name {stack_name} " +
                "--no-enable-termination-protection"
            )
            click.secho(msg.format(stack_name=stack_name), fg="red")
        elif "AccessDeniedException" in e.response["Error"]["Message"]:
            click.secho(
                "The user account does not have access to delete the stack. \n" +
                "Please update the resources required to delete the stack and the required user policies.",
                fg="red",
            )
        else:
            click.secho(
                "Failed to destroy Stack: {}".format(
                    str(e.response["Error"]["Message"])
                ),
                fg="red",
            )

        sys.exit(1)

    if wait:
        waiter = cfn.get_waiter("stack_delete_complete")
        click.secho("Waiting for stack {} to be deleted".format(stack_name), fg="red")
        try:
            delay = 15
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={"Delay": delay, "MaxAttemps": wait_time / delay},
            )
        except WaiterError as e:
            click.secho(
                "Failed to delete stack {} because {}".format(stack_name, str(e)),
                fg="red",
            )
            sys.exit(1)

    click.secho("Destroyed stack {}!".format(stack_name), fg="cyan")
