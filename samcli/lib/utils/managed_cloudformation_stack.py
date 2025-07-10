"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import logging
from collections.abc import Collection
from typing import Dict, List, Optional, Union, cast

import boto3
import click
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, NoRegionError, ProfileNotFound

from samcli.commands.exceptions import AWSServiceClientError, RegionError, UserException

LOG = logging.getLogger(__name__)


class ManagedStackError(UserException):
    def __init__(self, ex):
        self.ex = ex
        message_fmt = f"Failed to create managed resources: {ex}"
        super().__init__(message=message_fmt.format(ex=self.ex))


class StackOutput:
    def __init__(self, stack_output: List[Dict[str, str]]):
        self._stack_output: List[Dict[str, str]] = stack_output

    def get(self, key) -> Optional[str]:
        try:
            return next(o for o in self._stack_output if o.get("OutputKey") == key).get("OutputValue")
        except StopIteration:
            return None


def update_stack(
    region: Optional[str],
    stack_name: str,
    template_body: str,
    profile: Optional[str] = None,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
) -> StackOutput:
    """
    create or update a CloudFormation stack

    Parameters
    ----------
    region: str
        AWS region for the CloudFormation stack
    stack_name: str
        CloudFormation stack name
    template_body: str
        CloudFormation template's content
    profile: Optional[str]
        AWS named profile for the AWS account
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]]
        Values of template parameters, if any.

    Returns
    -------
    StackOutput:
        Stack output section(list of OutputKey, OutputValue pairs)
    """
    try:
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region if region else None)
            cloudformation_client = session.client("cloudformation")
        else:
            cloudformation_client = boto3.client(
                "cloudformation", config=Config(region_name=region if region else None)
            )
    except ProfileNotFound as ex:
        raise AWSServiceClientError(
            f"Error Setting Up Managed Stack Client: the provided AWS name profile '{profile}' is not found. "
            "please check the documentation for setting up a named profile: "
            "https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html"
        ) from ex
    except NoCredentialsError as ex:
        raise AWSServiceClientError(
            "Error Setting Up Managed Stack Client: Unable to resolve credentials for the AWS SDK for Python client. "
            "Please see their documentation for options to pass in credentials: "
            "https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html"
        ) from ex
    except NoRegionError as ex:
        raise RegionError(
            "Error Setting Up Managed Stack Client: Unable to resolve a region. "
            "Please provide a region via the --region parameter or by the AWS_DEFAULT_REGION environment variable."
        ) from ex
    return _create_or_update_stack(cloudformation_client, stack_name, template_body, parameter_overrides)


def manage_stack(
    region: Optional[str],
    stack_name: str,
    template_body: str,
    profile: Optional[str] = None,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
) -> StackOutput:
    """
    get or create a CloudFormation stack

    Parameters
    ----------
    region: str
        AWS region for the CloudFormation stack
    stack_name: str
        CloudFormation stack name
    template_body: str
        CloudFormation template's content
    profile: Optional[str]
        AWS named profile for the AWS account
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]]
        Values of template parameters, if any.

    Returns
    -------
    StackOutput:
        Stack output section(list of OutputKey, OutputValue pairs)
    """
    try:
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region if region else None)
            cloudformation_client = session.client("cloudformation")
        else:
            cloudformation_client = boto3.client(
                "cloudformation", config=Config(region_name=region if region else None)
            )
    except ProfileNotFound as ex:
        raise AWSServiceClientError(
            f"Error Setting Up Managed Stack Client: the provided AWS name profile '{profile}' is not found. "
            "please check the documentation for setting up a named profile: "
            "https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html"
        ) from ex
    except NoCredentialsError as ex:
        raise AWSServiceClientError(
            "Error Setting Up Managed Stack Client: Unable to resolve credentials for the AWS SDK for Python client. "
            "Please see their documentation for options to pass in credentials: "
            "https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html"
        ) from ex
    except NoRegionError as ex:
        raise RegionError(
            "Error Setting Up Managed Stack Client: Unable to resolve a region. "
            "Please provide a region via the --region parameter or by the AWS_DEFAULT_REGION environment variable."
        ) from ex
    return _create_or_get_stack(cloudformation_client, stack_name, template_body, parameter_overrides)


# Todo Add _update_stack to handle the case when the values of the stack parameter got changed
def _create_or_get_stack(
    cloudformation_client,
    stack_name: str,
    template_body: str,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
) -> StackOutput:
    try:
        ds_resp = cloudformation_client.describe_stacks(StackName=stack_name)
        stacks = ds_resp["Stacks"]
        stack = stacks[0]
        _check_sanity_of_stack(stack)
        stack_outputs = cast(List[Dict[str, str]], stack["Outputs"])
        return StackOutput(stack_outputs)
    except ClientError:
        LOG.debug("Managed S3 stack [%s] not found. Creating a new one.", stack_name)

    try:
        stack = _create_stack(
            cloudformation_client, stack_name, template_body, parameter_overrides
        )  # exceptions are not captured from subcommands
        _check_sanity_of_stack(stack)
        stack_outputs = cast(List[Dict[str, str]], stack["Outputs"])
        return StackOutput(stack_outputs)
    except (ClientError, BotoCoreError) as ex:
        LOG.debug("Failed to create managed resources", exc_info=ex)
        raise ManagedStackError(str(ex)) from ex


def _create_or_update_stack(
    cloudformation_client,
    stack_name: str,
    template_body: str,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
) -> StackOutput:
    try:
        cloudformation_client.describe_stacks(StackName=stack_name)
        stack = _update_stack(cloudformation_client, stack_name, template_body, parameter_overrides)
        _check_sanity_of_stack(stack)
        stack_outputs = cast(List[Dict[str, str]], stack["Outputs"])
        return StackOutput(stack_outputs)
    except ClientError:
        LOG.debug("Managed S3 stack [%s] not found. Creating a new one.", stack_name)

    try:
        stack = _create_stack(
            cloudformation_client, stack_name, template_body, parameter_overrides
        )  # exceptions are not captured from subcommands
        _check_sanity_of_stack(stack)
        stack_outputs = cast(List[Dict[str, str]], stack["Outputs"])
        return StackOutput(stack_outputs)
    except (ClientError, BotoCoreError) as ex:
        LOG.debug("Failed to create managed resources", exc_info=ex)
        raise ManagedStackError(str(ex)) from ex


def _check_sanity_of_stack(stack):
    stack_name = stack.get("StackName")
    tags = stack.get("Tags", None)
    outputs = stack.get("Outputs", None)

    # For some edge cases, stack could be in invalid state
    # Check if stack information contains the Tags and Outputs as we expected
    if tags is None or outputs is None:
        stack_state = stack.get("StackStatus", None)
        msg = (
            f"Stack {stack_name} is missing Tags and/or Outputs information and therefore not in a "
            f"healthy state (Current state:{stack_state}). Failing as the stack was likely not created "
            f"by the AWS SAM CLI"
        )
        raise UserException(msg)

    # Sanity check for non-none stack? Sanity check for tag?
    try:
        sam_cli_tag = next(t for t in tags if t["Key"] == "ManagedStackSource")
        if not sam_cli_tag["Value"] == "AwsSamCli":
            msg = (
                "Stack "
                + stack_name
                + " ManagedStackSource tag shows "
                + sam_cli_tag["Value"]
                + " which does not match the AWS SAM CLI generated tag value of AwsSamCli. "
                "Failing as the stack was likely not created by the AWS SAM CLI."
            )
            raise UserException(msg)
    except StopIteration as ex:
        msg = (
            "Stack  " + stack_name + " exists, but the ManagedStackSource tag is missing. "
            "Failing as the stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg) from ex


def _create_stack(
    cloudformation_client,
    stack_name: str,
    template_body: str,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
):
    click.echo("\tCreating the required resources...")
    change_set_name = "InitialCreation"
    parameters = _generate_stack_parameters(parameter_overrides)
    change_set_resp = cloudformation_client.create_change_set(
        StackName=stack_name,
        TemplateBody=template_body,
        Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
        ChangeSetType="CREATE",
        ChangeSetName=change_set_name,  # this must be unique for the stack, but we only create so that's fine
        Capabilities=["CAPABILITY_IAM"],
        Parameters=parameters,
    )
    stack_id = change_set_resp["StackId"]
    change_waiter = cloudformation_client.get_waiter("change_set_create_complete")
    change_waiter.wait(
        ChangeSetName=change_set_name, StackName=stack_name, WaiterConfig={"Delay": 15, "MaxAttempts": 60}
    )
    cloudformation_client.execute_change_set(ChangeSetName=change_set_name, StackName=stack_name)
    stack_waiter = cloudformation_client.get_waiter("stack_create_complete")
    stack_waiter.wait(StackName=stack_id, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    ds_resp = cloudformation_client.describe_stacks(StackName=stack_name)
    stacks = ds_resp["Stacks"]
    click.echo("\tSuccessfully created!")
    return stacks[0]


def _update_stack(
    cloudformation_client,
    stack_name: str,
    template_body: str,
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
):
    click.echo("\tUpdating the required resources...")
    parameters = _generate_stack_parameters(parameter_overrides)
    us_resp = cloudformation_client.update_stack(
        StackName=stack_name,
        TemplateBody=template_body,
        Tags=[{"Key": "ManagedStackSource", "Value": "AwsSamCli"}],
        Capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
        Parameters=parameters,
    )
    stack_id = us_resp["StackId"]
    stack_waiter = cloudformation_client.get_waiter("stack_update_complete")
    stack_waiter.wait(StackName=stack_id, WaiterConfig={"Delay": 15, "MaxAttempts": 60})
    ds_resp = cloudformation_client.describe_stacks(StackName=stack_name)
    stacks = ds_resp["Stacks"]
    click.echo("\tSuccessfully updated!")
    return stacks[0]


def _generate_stack_parameters(
    parameter_overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
) -> List[Dict[str, str]]:
    parameters = []
    if parameter_overrides:
        for key, value in parameter_overrides.items():
            norm_value = value
            if isinstance(norm_value, Collection) and not isinstance(norm_value, str):
                # Assumption: values don't include commas or spaces. Need to refactor to handle such a case if needed.
                norm_value = ",".join(norm_value)
            parameters.append({"ParameterKey": key, "ParameterValue": norm_value})
    return parameters
