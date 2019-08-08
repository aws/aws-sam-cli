"""
CLI command for "deploy" command
"""
import sys
import uuid
from datetime import datetime

import boto3
import click
from botocore.exceptions import ClientError, WaiterError
from click import secho

from samcli.cli.main import pass_context, common_options
from samcli.lib.samlib.cloudformation_command import execute_command
from samcli.commands.exceptions import UserException
from samcli.lib.telemetry.metrics import track_command

SHORT_HELP = "Deploy an AWS SAM application. This is an alias for 'aws cloudformation deploy'."

HELP_TEXT = """The sam deploy command creates a Cloudformation Stack and deploys your resources.

\b
e.g. sam deploy --template-file packaged.yaml --stack-name sam-app --capabilities CAPABILITY_IAM

\b
"""


@click.command("deploy", short_help=SHORT_HELP, context_settings={"ignore_unknown_options": True}, help=HELP_TEXT)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
@click.option('-t', '--template', '--template-file',
              required=True,
              type=click.Path(),
              help="The path where your AWS SAM template is located")
@click.option('--stack-name',
              required=True,
              help="The name of the AWS CloudFormation stack you're deploying to. "
                   "If you specify an existing stack, the command updates the stack. "
                   "If you specify a new stack, the command creates it.")
@click.option('--s3-bucket',
              help=" The name of  the  S3  bucket  where  this  command"
                   "uploads  your CloudFormation template. This is required the deployments"
                   "of templates sized greater than 51,200 bytes")
@click.option('--force-upload',
              help="Indicates whether to override  existing  files"
                   "in  the  S3  bucket. Specify this flag to upload artifacts even if they"
                   "match existing artifacts in the S3 bucket.")
@click.option('--kms-key-id',
              help=" The ID of an AWS KMS key that the command uses to"
                   "encrypt artifacts that are at rest in the S3 bucket.")
@click.option('--parameter-overrides', multiple=True,
              help="A list of parameter structures that spec-"
                   "ify input parameters for your stack  template.  If  you're  updating  a"
                   "stack  and  you don't specify a parameter, the command uses the stack's"
                   "existing value. For new stacks, you must specify parameters that  don't"
                   "have  a  default  value.  Syntax: ParameterKey1=ParameterValue1 Parame-"
                   "terKey2=ParameterValue2 ...")
@click.option('--capabilities', multiple=True,
              help=" A list of  capabilities  that  you  must  specify"
                   "before  AWS  Cloudformation  can create certain stacks. Some stack tem-"
                   "plates might include resources that can affect permissions in your  AWS"
                   "account,  for  example, by creating new AWS Identity and Access Manage-"
                   "ment (IAM) users. For those stacks,  you  must  explicitly  acknowledge"
                   "their  capabilities by specifying this parameter. The only valid values"
                   "are CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If you have IAM resources,"
                   "you  can specify either capability. If you have IAM resources with cus-"
                   "tom names, you must specify CAPABILITY_NAMED_IAM. If you don't  specify"
                   "this  parameter, this action returns an InsufficientCapabilities error. "
                   "Valid values are CAPABILITY_IAM, CAPABILITY_NAMED_IAM, CAPABILITY_AUTO_EXPAND")
@click.option('--no-execute-changeset', '--dry-run', 'no_execute_changeset',
              is_flag=True,
              help="Indicates  whether  to  execute  the"
                   "change  set.  Specify  this flag if you want to view your stack changes"
                   "before executing the change set. The command creates an AWS CloudForma-"
                   "tion  change set and then exits without executing the change set. After"
                   "you view the change set, execute it to implement your changes.")
@click.option('--role-arn',
              help=" The Amazon Resource Name (ARN) of an  AWS  Identity"
                   "and  Access  Management (IAM) role that AWS CloudFormation assumes when"
                   "executing the change set.")
@click.option('--notification-arns',
              help=" Amazon  Simple  Notification  Service  topic"
                   "Amazon  Resource  Names  (ARNs) that AWS CloudFormation associates with"
                   "the stack.")
@click.option('--fail-on-empty-changeset/--no-fail-on-empty-changeset',
              help=" Specify  if  the CLI should return a non-zero exit code if there are no"
                   "changes to be made to the stack. The default behavior is  to  return  a"
                   "non-zero exit code.")
@click.option('--tags', multiple=True,
              help=" A list of tags to associate with the stack that is cre-"
                   "ated or updated. AWS  CloudFormation  also  propagates  these  tags  to"
                   "resources   in   the   stack  if  the  resource  supports  it.  Syntax:"
                   "TagKey1=TagValue1 TagKey2=TagValue2 ...")
@click.option('-w', '--wait', required=False, is_flag=True, help="Option to wait for Stack deletion")
@click.option('--wait-time', required=False, type=click.INT,
              help="The time to wait for stack to delete in seconds. Used with --wait. The default is 5 minutes")
@common_options
@pass_context
@track_command
def cli(ctx, args, template_file, stack_name, s3_bucket, force_upload, kms_key_id, parameter_overrides, capabilities,
        no_execute_changeset, role_arn, notification_arns, fail_on_empty_changeset, tags, wait, wait_time=300):
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing
    do_cli(args, template_file, stack_name, s3_bucket, force_upload, kms_key_id, parameter_overrides, capabilities,
           no_execute_changeset, role_arn, notification_arns, fail_on_empty_changeset, tags, wait,
           wait_time)  # pragma: no cover


def generate_stack_changes(client, change_set_name, stack_name):
    paginator = client.get_paginator('describe_change_set')
    response_iterator = paginator.paginate(
        ChangeSetName=change_set_name,
        StackName=stack_name,
    )
    changes = {"Add": [], "Modify": [], "Remove": []}
    for item in response_iterator:
        changes = item.get("Changes")
        for change in changes:
            resource_props = change.get("ResourceChange")
            action = resource_props.get("Action")
            logical_id = resource_props.get("LogicalResourceId")
            resource_type = resource_props.get("ResourceType")
            changes[action].append({"LogicalResourceId": logical_id, "ResourceType": resource_type})
    return changes


def do_cli(args, template_file, stack_name, s3_bucket, force_upload, kms_key_id, parameter_overrides, capabilities,
           no_execute_changeset, role_arn, notification_arns, fail_on_empty_changset, tags, wait, wait_time):
    client = boto3.client('cloudformation')

    try:
        change_set_name = str(uuid.uuid4()) + str(datetime.now())
        response = client.create_change_set(
            StackName=stack_name,
            TemplateBody=template_file,
            TemplateURL=s3_bucket,  # --s3-bucket
            Parameters=[  # parameters
                {
                    'ParameterKey': item.split("=")[0],
                    'ParameterValue': item.split("=")[1]
                }
                for item in parameter_overrides
            ],
            NotificationARNs=[
                notification_arns,  # notification arns
            ],
            Capabilities=capabilities,
            RoleARN=role_arn,  # role-arn
            Tags=[  # tags
                {
                    'Key': item.split("=")[0],
                    'Value': item.split("=")[1]
                }
                for item in tags
            ],
            ChangeSetName=change_set_name,
        )
        change_set_id = response.get("Id")
        changes = generate_stack_changes(client, change_set_id, stack_name)

        if len(changes.get("Add") + changes.get("Modify") + changes.get("Remove")) == 0 and fail_on_empty_changset:
            click.secho("The stack {} has an empty Change Set".format(stack_name), fg="red")
            sys.exit(1)

        if changes.get("Add"):
            secho("Resources Added")
        for change in changes.get("Add"):
            secho("+ " + change.get("LogicalResourceId") + " " + change.get("ResourceType"))

        if changes.get("Modify"):
            secho("Resources Modified")
        for change in changes.get("Modify"):
            secho("~ " + change.get("LogicalResourceId") + " " + change.get("ResourceType"))

        if changes.get("Remove"):
            secho("Resources Removed")
        for change in changes.get("Remove"):
            secho("- " + change.get("LogicalResourceId") + " " + change.get("ResourceType"))

        if no_execute_changeset:
            sys.exit(0)

        response = client.execute_change_set(
            ChangeSetName=change_set_name,
            StackName=stack_name,
        )

    except ClientError as e:
        if "AccessDeniedException" in e.response["Error"]["Message"]:
            click.secho(
                'The user account does not have access to create/update the stack. \n' +
                'Please update the resources required to create/update the stack and the required user policies.',
                fg="red")
        else:
            click.secho("Failed to destroy Stack: {}".format(str(e.response["Error"]["Message"])), fg="red")

        sys.exit(1)

    if wait or wait_time:
        waiter = client.get_waiter('stack_delete_complete')
        try:
            delay = 15
            waiter.wait(StackName=stack_name,
                        WaiterConfig={
                            'Delay': delay,
                            'MaxAttemps': wait_time / delay
                        })
        except WaiterError as e:
            click.secho("Failed to delete stack {} because {}".format(stack_name, str(e)), fg="red")
            sys.exit(1)
    paginator = client.get_paginator('describe_stack_events')

    response_iterator = paginator.paginate(
        StackName=stack_name
    )
    events = []
    failure_exists = False
    for page in response_iterator:
        for event in page.get("StackEvents"):
            if "FAILED" in event.get("ResourceStatus"):
                failure_exists = True

            if failure_exists:
                events.append(event)

    if failure_exists:
        secho("The stack {} changeset failed".format(stack_name), fg="red")
        for event in reversed(events):
            logical_id = event.get("LogicalResourceId")
            resource_type = event.get("ResourceType")
            resource_status = event.get("ResourceStatusReason")
            reason = event.get("ResourceStatusReason")
            secho("The resource {} of type {} has status {}:  {}".format(logical_id, resource_type, resource_status,
                                                                         reason), fg="red")
