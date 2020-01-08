"""
Utilities for sam deploy command
"""

import json
import click


def print_deploy_args(stack_name, s3_bucket, region, capabilities, parameter_overrides, confirm_changeset):
    """
    Print a table of the values that are used during a sam deploy

    Example below:

        Deploying with following values
        ===============================
        Stack name                 : sam-app
        Region                     : us-east-1
        Confirm changeset          : False
        Deployment s3 bucket       : aws-sam-cli-managed-default-samclisourcebucket-abcdef
        Capabilities               : ["CAPABILITY_IAM"]
        Parameter overrides        : {'MyParamater': '***', 'Parameter2': 'dd'}

    :param stack_name: Name of the stack used during sam deploy
    :param s3_bucket: Name of s3 bucket used for packaging code artifacts
    :param region: Name of region to which the current sam/cloudformation stack will be deployed to.
    :param capabilities: Corresponding IAM capabilities to be used during the stack deploy.
    :param parameter_overrides: Cloudformation parameter overrides to be supplied based on the stack's template
    :param confirm_changeset: Prompt for changeset to be confirmed before going ahead with the deploy.
    :return:
    """

    _parameters = parameter_overrides.copy()
    for key, value in _parameters.items():
        if isinstance(value, dict):
            _parameters[key] = value.get("Value", value) if not value.get("Hidden") else "*" * len(value.get("Value"))

    capabilities_string = json.dumps(capabilities)

    click.secho("\n\tDeploying with following values\n\t===============================", fg="yellow")
    click.echo(f"\tStack name                 : {stack_name}")
    click.echo(f"\tRegion                     : {region}")
    click.echo(f"\tConfirm changeset          : {confirm_changeset}")
    click.echo(f"\tDeployment s3 bucket       : {s3_bucket}")
    click.echo(f"\tCapabilities               : {capabilities_string}")
    click.echo(f"\tParameter overrides        : {_parameters}")

    click.secho("\nInitiating deployment\n=====================", fg="yellow")


def sanitize_parameter_overrides(parameter_overrides):
    """
    Get sanitized parameter override values based on if the workflow went via a guided deploy to set the
    parameter overrides for deployment. If a guided deploy was followed the parameter overrides consists
    of additional information such as if a given parameter's value is hidden or not.
    :param parameter_overrides: dictionary of parameter key values.
    :return:
    """
    return {key: value.get("Value") if isinstance(value, dict) else value for key, value in parameter_overrides.items()}
